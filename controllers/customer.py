# -*- coding: utf-8 -*-
import base64
import logging
from odoo import http
from odoo.http import request
import werkzeug

_logger = logging.getLogger(__name__)


class CustomerSupportCustomer(http.Controller):

    @http.route("/customer_support/dashboard", type="http", auth="user", website=True)
    def support_dashboard(self, **kw):
        try:
            user = request.env.user
            if user.id == request.env.ref("base.public_user").id:
                return werkzeug.utils.redirect(
                    "/customer_support/login?error=Please login to access dashboard"
                )
            if user.has_group("base.group_system"):
                return werkzeug.utils.redirect("/customer_support/admin_dashboard")
            tickets = (
                request.env["customer.support"]
                .search([("customer_id", "=", user.partner_id.id)])
                .sorted(key=lambda r: r.create_date, reverse=True)
            )
            ticket_counts = {
                "new": len(tickets.filtered(lambda t: t.state == "new")),
                "in_progress": len(
                    tickets.filtered(lambda t: t.state == "in_progress")
                ),
                "resolved": len(tickets.filtered(lambda t: t.state == "resolved")),
                "closed": len(tickets.filtered(lambda t: t.state == "closed")),
                "total": len(tickets),
            }
            return request.render(
                "customer_support.portal_dashboard",
                {
                    "user": user,
                    "tickets": tickets,
                    "ticket_counts": ticket_counts,
                    "analytics": {},
                    "performance": {},
                    "page_name": "dashboard",
                },
            )
        except Exception as e:
            _logger.error(f"Dashboard error: {str(e)}")
            return werkzeug.utils.redirect(
                "/customer_support/login?error=Error loading dashboard"
            )

    @http.route(
        "/customer_support/create_ticket", type="http", auth="user", website=True
    )
    def create_ticket_form(self, **kw):
        try:
            user = request.env.user
            if user.id == request.env.ref("base.public_user").id:
                return werkzeug.utils.redirect(
                    "/customer_support/login?error=Please login"
                )
            projects = (
                request.env["customer_support.project"]
                .sudo()
                .search([("active", "=", True)])
            )
            return request.render(
                "customer_support.create_ticket_form",
                {
                    "user": user,
                    "projects": projects,
                    "error": kw.get("error", ""),
                    "page_name": "create_ticket",
                },
            )
        except Exception as e:
            _logger.error(f"Create ticket form error: {str(e)}")
            return werkzeug.utils.redirect("/customer_support/dashboard")

    @http.route(
        "/customer_support/submit_ticket",
        type="http",
        auth="user",
        methods=["POST"],
        website=True,
        csrf=True,
    )
    def submit_ticket(self, **post):
        try:
            user = request.env.user

            _logger.info(f"POST data type: {type(post)}")

            # Robust post data normalization
            post_dict = {}
            if hasattr(post, "items"):
                post_dict = dict(post)
            elif isinstance(post, (list, tuple)):
                post_dict = dict(post)
            else:
                try:
                    post_dict = dict(post)
                except Exception as conv_err:
                    _logger.error(
                        f"Cannot convert post to dict: {type(post)}, {conv_err}"
                    )
                    return werkzeug.utils.redirect(
                        "/customer_support/create_ticket?error=Invalid form data"
                    )

            subject = post_dict.get("subject", "").strip()
            description = post_dict.get("description", "").strip()
            project_id = post_dict.get("project_id")

            if not subject:
                return werkzeug.utils.redirect(
                    "/customer_support/create_ticket?error=Subject is required"
                )
            if not description:
                return werkzeug.utils.redirect(
                    "/customer_support/create_ticket?error=Description is required"
                )
            if not project_id:
                return werkzeug.utils.redirect(
                    "/customer_support/create_ticket?error=Project is required"
                )

            ticket = (
                request.env["customer.support"]
                .sudo()
                .create(
                    {
                        "subject": subject,
                        "description": description,
                        "priority": post_dict.get("priority", "medium"),
                        "customer_id": user.partner_id.id,
                        "project_id": int(project_id),
                        "state": "new",
                    }
                )
            )

            # Handle attachments
            try:
                if hasattr(request, "httprequest") and hasattr(
                    request.httprequest, "files"
                ):
                    for file_key in request.httprequest.files:
                        uploaded_file = request.httprequest.files[file_key]
                        if uploaded_file and uploaded_file.filename:
                            file_data = uploaded_file.read()
                            if file_data:
                                request.env["ir.attachment"].sudo().create(
                                    {
                                        "name": uploaded_file.filename,
                                        "type": "binary",
                                        "datas": base64.b64encode(file_data).decode(
                                            "utf-8"
                                        ),  # FIXED
                                        "res_model": "customer.support",
                                        "res_id": ticket.id,
                                        "mimetype": uploaded_file.content_type
                                        or "application/octet-stream",
                                    }
                                )
                                _logger.info(
                                    f"Attachment added: {uploaded_file.filename}"
                                )
            except Exception as attach_err:
                _logger.warning(
                    f"Attachment processing error (ticket still created): {attach_err}"
                )

            _logger.info(
                f"Ticket created: {ticket.name} by {user.name} for project {project_id}"
            )

            return werkzeug.utils.redirect(
                "/customer_support/dashboard?success=Ticket submitted successfully"
            )

        except Exception as e:
            _logger.exception(f"Submit ticket error: {str(e)}")
            return werkzeug.utils.redirect(
                "/customer_support/create_ticket?error=Error creating ticket. Please try again."
            )
