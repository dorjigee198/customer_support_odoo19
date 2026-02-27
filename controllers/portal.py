# -*- coding: utf-8 -*-
import base64
from odoo import http, fields
from odoo.http import request
import werkzeug
import logging
import json

_logger = logging.getLogger(__name__)


class CustomerSupportPortal(http.Controller):

    @http.route("/customer_support", type="http", auth="public", website=True)
    def landing_page(self, **kw):
        """Landing page - first page visitors see"""
        return request.render("customer_support.landing_page")

    @http.route("/customer_support/login", type="http", auth="public", website=True)
    def support_login(self, **kw):
        """Display custom login page"""
        return request.render(
            "customer_support.portal_login_page",
            {
                "error": kw.get("error", ""),
            },
        )

    @http.route(
        "/customer_support/authenticate",
        type="http",
        auth="public",
        methods=["POST"],
        website=True,
        csrf=False,
    )
    def support_authenticate(self, **post):
        """Handle login authentication"""
        try:
            email = post.get("email", "").strip()
            password = post.get("password", "")

            _logger.info(f"Login attempt for email/login: {email}")

            if not email or not password:
                return werkzeug.utils.redirect(
                    "/customer_support/login?error=Email and password are required"
                )

            db = request.session.db
            if not db:
                return werkzeug.utils.redirect(
                    "/customer_support/login?error=Database connection error"
                )

            uid = False
            users = (
                request.env["res.users"]
                .sudo()
                .search(["|", ("login", "=", email), ("email", "=", email)])
            )
            for u in users:
                try:
                    auth_info = request.session.authenticate(
                        request.env,
                        {"type": "password", "login": u.login, "password": password},
                    )
                    uid = auth_info.get("uid") if auth_info else False
                except Exception as ex:
                    _logger.exception(f"authenticate raised for user {u.login}: {ex}")
                    uid = False
                if uid:
                    break

            if uid:
                user = request.env["res.users"].browse(uid)
                if not user.active:
                    request.session.logout()
                    return werkzeug.utils.redirect(
                        "/customer_support/login?error=Your account is inactive"
                    )
                if user.has_group("base.group_system"):
                    request.session["customer_support_login"] = True
                    return werkzeug.utils.redirect("/customer_support/admin_dashboard")

                elif user.has_group("base.group_portal"):
                    request.session["customer_support_login"] = True
                    return werkzeug.utils.redirect("/customer_support/dashboard")

                elif user.has_group("base.group_user"):
                    request.session["customer_support_login"] = True
                    return werkzeug.utils.redirect(
                        "/customer_support/support_dashboard"
                    )
                else:
                    request.session.logout()
                    return werkzeug.utils.redirect(
                        "/customer_support/login?error=You do not have access to the customer support portal"
                    )

            return werkzeug.utils.redirect(
                "/customer_support/login?error=Invalid email or password"
            )

        except Exception as e:
            _logger.error(f"Login processing error: {str(e)}")
            return werkzeug.utils.redirect(
                "/customer_support/login?error=An error occurred during login. Please try again."
            )

    @http.route("/customer_support/dashboard", type="http", auth="user", website=True)
    def support_dashboard(self, **kw):
        """Customer dashboard"""
        try:
            user = request.env.user
            if user.id == request.env.ref("base.public_user").id:
                return werkzeug.utils.redirect(
                    "/customer_support/login?error=Please login to access dashboard"
                )

            # Redirect admin users to admin dashboard
            if user.has_group("base.group_system"):
                return werkzeug.utils.redirect("/customer_support/admin_dashboard")

            tickets = (
                request.env["customer.support"]
                .search([("customer_id", "=", user.partner_id.id)])
                .sorted(key=lambda r: r.create_date, reverse=True)
            )

            ticket_counts = {
                "new": len(tickets.filtered(lambda t: t.state == "new")),
                "open": len(tickets.filtered(lambda t: t.state == "open")),
                "in_progress": len(
                    tickets.filtered(lambda t: t.state == "in_progress")
                ),
                "resolved": len(tickets.filtered(lambda t: t.state == "resolved")),
                "closed": len(tickets.filtered(lambda t: t.state == "closed")),
                "total": len(tickets),
            }

            analytics = {}
            performance = {}
            try:
                dashboard_model = request.env["customer_support.dashboard"]
                analytics = dashboard_model.get_ticket_analytics(user.id)
                performance = dashboard_model.get_user_performance(user.id)
            except Exception as e:
                _logger.warning(f"Dashboard analytics failed: {str(e)}")
                analytics = {
                    "open_tickets": ticket_counts.get("new", 0)
                    + ticket_counts.get("in_progress", 0),
                    "total_tickets": ticket_counts.get("total", 0),
                    "high_priority": 0,
                    "urgent": 0,
                    "avg_open_hours": 0,
                    "total_hours": 0,
                    "avg_high_hours": 0,
                    "avg_urgent_hours": 0,
                    "resolved_tickets": ticket_counts.get("resolved", 0)
                    + ticket_counts.get("closed", 0),
                    "solve_rate": 0,
                    "high_resolved": 0,
                    "urgent_resolved": 0,
                }
                performance = {
                    "today_closed": 0,
                    "avg_resolve_rate": 0,
                    "daily_target": 80.00,
                    "achievement": 0,
                    "sample_performance": 85.00,
                }

            return request.render(
                "customer_support.portal_dashboard",
                {
                    "user": user,
                    "tickets": tickets,
                    "ticket_counts": ticket_counts,
                    "analytics": analytics,
                    "performance": performance,
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
        """Customer ticket creation form"""
        try:
            user = request.env.user
            if user.id == request.env.ref("base.public_user").id:
                return werkzeug.utils.redirect(
                    "/customer_support/login?error=Please login to access tickets"
                )

            return request.render(
                "customer_support.create_ticket_form",
                {
                    "user": user,
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
        """Handle ticket submission and attachments safely"""
        try:
            user = request.env.user

            # Log the type of post data received for debugging
            _logger.info(f"POST data type: {type(post)}")

            # Normalize post data to dict - FIX FOR THE BUG
            post_dict = {}

            if hasattr(post, "items"):
                # It's already a dict-like object
                post_dict = dict(post)
            elif isinstance(post, (list, tuple)):
                # It's a list of tuples
                post_dict = dict(post)
            else:
                # Fallback - try to convert
                try:
                    post_dict = dict(post)
                except Exception as conv_err:
                    _logger.error(
                        f"Cannot convert post to dict: {type(post)}, {conv_err}"
                    )
                    return werkzeug.utils.redirect(
                        "/customer_support/create_ticket?error=Invalid form data"
                    )

            # Validate required fields
            subject = post_dict.get("subject", "").strip()
            description = post_dict.get("description", "").strip()

            if not subject:
                return werkzeug.utils.redirect(
                    "/customer_support/create_ticket?error=Subject is required"
                )

            if not description:
                return werkzeug.utils.redirect(
                    "/customer_support/create_ticket?error=Description is required"
                )

            # Create ticket
            ticket = request.env["customer.support"].create(
                {
                    "subject": subject,
                    "description": description,
                    "priority": post_dict.get("priority", "medium"),
                    "customer_id": user.partner_id.id,
                    "state": "new",
                }
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
                                request.env["ir.attachment"].create(
                                    {
                                        "name": uploaded_file.filename,
                                        "type": "binary",
                                        "datas": base64.b64encode(file_data),
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

            _logger.info(f"Ticket created: {ticket.name} by {user.name}")

            return werkzeug.utils.redirect(
                "/customer_support/dashboard?success=Ticket submitted successfully"
            )

        except Exception as e:
            _logger.exception(f"Submit ticket error: {str(e)}")
            return werkzeug.utils.redirect(
                "/customer_support/create_ticket?error=Error creating ticket. Please try again."
            )

    @http.route(
        "/customer_support/admin_dashboard", type="http", auth="user", website=True
    )
    def admin_dashboard(self, **kw):
        """Admin dashboard"""
        user = request.env.user
        if not user.has_group("base.group_system"):
            return werkzeug.utils.redirect(
                "/customer_support/dashboard"
            )  # block non-admins

        tickets = (
            request.env["customer.support"]
            .search([])
            .sorted(key=lambda r: r.create_date, reverse=True)
        )

        ticket_counts = {
            "new": len(tickets.filtered(lambda t: t.state == "new")),
            "open": len(tickets.filtered(lambda t: t.state == "open")),
            "resolved": len(tickets.filtered(lambda t: t.state == "resolved")),
            "closed": len(tickets.filtered(lambda t: t.state == "closed")),
            "total": len(tickets),
        }

        return request.render(
            "customer_support.admin_dashboard",
            {
                "user": user,
                "tickets": tickets,
                "ticket_counts": ticket_counts,
                "page_name": "admin_dashboard",
                "analytics": {                  
                    "open_tickets": ticket_counts.get("new", 0) + ticket_counts.get("open", 0),
                    "total_tickets": ticket_counts.get("total", 0),
                    "high_priority": 0,
                    "urgent": 0,
                    "avg_open_hours": 0,
                    "total_hours": 0,
                    "avg_high_hours": 0,
                    "avg_urgent_hours": 0,
                    "resolved_tickets": ticket_counts.get("resolved", 0) + ticket_counts.get("closed", 0),
                    "solve_rate": 0,
                    "high_resolved": 0,
                    "urgent_resolved": 0,
                },
                "performance": {                
                    "sample_performance": 85,
                    "today_closed": 0,
                    "avg_resolve_rate": 0,
                    "daily_target": 80,
                    "achievement": 0,
                },
            },
        )

    @http.route(
        "/customer_support/ticket/<int:ticket_id>",
        type="http",
        auth="user",
        website=True,
    )
    def view_ticket(self, ticket_id, **kw):
        """View ticket details"""
        try:
            user = request.env.user
            if user.id == request.env.ref("base.public_user").id:
                return werkzeug.utils.redirect(
                    "/customer_support/login?error=Please login"
                )

            ticket = request.env["customer.support"].browse(ticket_id)
            if not ticket.exists():
                return werkzeug.utils.redirect(
                    "/customer_support/dashboard?error=Ticket not found"
                )

            is_admin = user.has_group("base.group_system")
            is_assigned = (
                ticket.assigned_to.id == user.id if ticket.assigned_to else False
            )
            is_customer = ticket.customer_id.id == user.partner_id.id

            focal_persons = []
            if is_admin:
                focal_persons = request.env["res.users"].search(
                    [("active", "=", True), ("id", "!=", 1)]
                )

            # ============ RETRIEVE MESSAGES FOR DISPLAY ============
            activities = []
            
            # METHOD 1: Try using message_ids from ticket
            try:
                if hasattr(ticket, 'message_ids') and ticket.message_ids:
                    # Filter only comment and notification types
                    activities = list(ticket.message_ids.filtered(
                        lambda m: m.message_type in ['comment', 'notification']
                    ).sorted(key=lambda r: r.date, reverse=True))
                    _logger.info(f"✓ Found {len(activities)} messages using message_ids for ticket {ticket_id}")
            except Exception as e:
                _logger.error(f"✗ message_ids failed: {str(e)}")
            
            # METHOD 2: Search mail.message table if METHOD 1 failed
            if not activities:
                try:
                    messages = request.env['mail.message'].sudo().search([
                        ('model', '=', 'customer.support'),
                        ('res_id', '=', ticket_id),
                        ('message_type', 'in', ['comment', 'notification'])
                    ], order='date desc')
                    activities = list(messages)
                    _logger.info(f"✓ Found {len(activities)} messages using mail.message search for ticket {ticket_id}")
                except Exception as e:
                    _logger.error(f"✗ mail.message search failed: {str(e)}")

            _logger.info(f"Ticket {ticket_id}: Passing {len(activities)} activities to template (type: {type(activities)})")

            return request.render(
                "customer_support.ticket_detail",
                {
                    "user": user,
                    "ticket": ticket,
                    "is_admin": is_admin,
                    "is_assigned": is_assigned,
                    "is_customer": is_customer,
                    "focal_persons": focal_persons,
                    "activities": activities,
                    "activities_count": len(activities),
                    "success": kw.get("success", ""),
                    "error": kw.get("error", ""),
                    "page_name": "ticket_detail",
                },
            )

        except Exception as e:
            _logger.error(f"View ticket error: {str(e)}")
            return werkzeug.utils.redirect(
                "/customer_support/dashboard?error=Error loading ticket"
            )

    @http.route(
        "/customer_support/ticket/<int:ticket_id>/post_message",
        type="http",
        auth="user",
        methods=["POST"],
        website=True,
        csrf=True,
    )
    def post_ticket_message(self, ticket_id, **post):
        """Handle posting messages to ticket communication"""
        try:
            ticket = request.env["customer.support"].sudo().browse(ticket_id)
            
            if not ticket.exists():
                return werkzeug.utils.redirect(
                    f"/customer_support/ticket/{ticket_id}?error=Ticket not found"
                )

            message = post.get('message', '').strip()
            
            if not message:
                return werkzeug.utils.redirect(
                    f"/customer_support/ticket/{ticket_id}?error=Message cannot be empty"
                )
            
            # Don't wrap in <p> tags - send as plain text and let Odoo handle formatting
            _logger.info(f"Attempting to post message to ticket {ticket_id}: {message}")
            
            # Try to post the message
            try:
                msg = ticket.message_post(
                    body=message,
                    message_type='comment',
                    subtype_xmlid='mail.mt_comment',
                )
                _logger.info(f"✓ Message posted successfully - Message ID: {msg.id if msg else 'N/A'}")
                success_msg = 'Message posted successfully'
            except Exception as e1:
                _logger.error(f"✗ message_post with subtype failed: {str(e1)}")
                try:
                    msg = ticket.message_post(
                        body=message,
                        message_type='comment',
                    )
                    _logger.info(f"✓ Message posted without subtype - Message ID: {msg.id if msg else 'N/A'}")
                    success_msg = 'Message posted successfully'
                except Exception as e2:
                    _logger.error(f"✗ message_post without subtype failed: {str(e2)}")
                    try:
                        msg = request.env['mail.message'].sudo().create({
                            'model': 'customer.support',
                            'res_id': ticket_id,
                            'body': message,
                            'message_type': 'comment',
                            'author_id': request.env.user.partner_id.id,
                        })
                        _logger.info(f"✓ Message created directly - Message ID: {msg.id}")
                        success_msg = 'Message posted successfully'
                    except Exception as e3:
                        _logger.error(f"✗ All methods failed: {str(e3)}")
                        success_msg = f'Error posting message: {str(e3)}'
            
            return werkzeug.utils.redirect(
                f"/customer_support/ticket/{ticket_id}?success={success_msg}"
            )

        except Exception as e:
            _logger.error(f"CRITICAL ERROR in post_message: {str(e)}")
            return werkzeug.utils.redirect(
                f"/customer_support/ticket/{ticket_id}?error={str(e)}"
            )

    @http.route(
        "/customer_support/ticket/message/<int:message_id>/delete",
        type="http",
        auth="user",
        methods=["POST"],
        csrf=False,
    )
    def delete_message(self, message_id, **kwargs):
        """Delete a message - AJAX endpoint"""
        try:
            message = request.env['mail.message'].sudo().browse(message_id)
            
            if not message.exists():
                return request.make_response(
                    json.dumps({'success': False, 'error': 'Message not found'}),
                    headers=[('Content-Type', 'application/json')]
                )
            
            # Check if user is the author or admin
            user = request.env.user
            is_admin = user.has_group("base.group_system")
            is_author = message.author_id.id == user.partner_id.id
            
            if not (is_admin or is_author):
                return request.make_response(
                    json.dumps({'success': False, 'error': 'You do not have permission to delete this message'}),
                    headers=[('Content-Type', 'application/json')]
                )
            
            ticket_id = message.res_id
            message.unlink()
            
            return request.make_response(
                json.dumps({'success': True, 'message': 'Message deleted successfully', 'ticket_id': ticket_id}),
                headers=[('Content-Type', 'application/json')]
            )
            
        except Exception as e:
            _logger.error(f"Delete message error: {str(e)}")
            return request.make_response(
                json.dumps({'success': False, 'error': str(e)}),
                headers=[('Content-Type', 'application/json')]
            )

    @http.route(
        "/customer_support/ticket/message/<int:message_id>/edit",
        type="http",
        auth="user",
        methods=["POST"],
        csrf=False,
    )
    def edit_message(self, message_id, new_body=None, **kwargs):
        """Edit a message - AJAX endpoint"""
        try:
            message = request.env['mail.message'].sudo().browse(message_id)
            
            if not message.exists():
                return request.make_response(
                    json.dumps({'success': False, 'error': 'Message not found'}),
                    headers=[('Content-Type', 'application/json')]
                )
            
            # Check if user is the author
            user = request.env.user
            is_author = message.author_id.id == user.partner_id.id
            
            if not is_author:
                return request.make_response(
                    json.dumps({'success': False, 'error': 'You can only edit your own messages'}),
                    headers=[('Content-Type', 'application/json')]
                )
            
            if not new_body or not new_body.strip():
                return request.make_response(
                    json.dumps({'success': False, 'error': 'Message cannot be empty'}),
                    headers=[('Content-Type', 'application/json')]
                )
            
            message.write({'body': new_body.strip()})
            
            return request.make_response(
                json.dumps({
                    'success': True,
                    'message': 'Message updated successfully',
                    'new_body': new_body.strip()
                }),
                headers=[('Content-Type', 'application/json')]
            )
            
        except Exception as e:
            _logger.error(f"Edit message error: {str(e)}")
            return request.make_response(
                json.dumps({'success': False, 'error': str(e)}),
                headers=[('Content-Type', 'application/json')]
            )

    @http.route(
        "/customer_support/ticket/<int:ticket_id>/assign",
        type="http",
        auth="user",
        methods=["POST"],
        website=True,
        csrf=True,
    )
    def assign_ticket(self, ticket_id, **post):
        try:
            user = request.env.user
            if not user.has_group("base.group_system"):
                return werkzeug.utils.redirect(
                    f"/customer_support/ticket/{ticket_id}?error=Access denied"
                )

            ticket = request.env["customer.support"].browse(ticket_id)
            if not ticket.exists():
                return werkzeug.utils.redirect(
                    "/customer_support/dashboard?error=Ticket not found"
                )

            # Normalize post data
            post_dict = dict(post) if not isinstance(post, dict) else post

            assigned_to = post_dict.get("assigned_to")
            if not assigned_to:
                return werkzeug.utils.redirect(
                    f"/customer_support/ticket/{ticket_id}?error=Please select a user to assign"
                )

            assigned_user_id = int(assigned_to)

            ticket.write(
                {
                    "assigned_to": assigned_user_id,
                    "state": "new",
                    "assigned_by": user.id,
                    "assigned_date": fields.Datetime.now(),
                }
            )

            _logger.info(f"Ticket {ticket.name} assigned to user {assigned_user_id}")

            return werkzeug.utils.redirect(
                f"/customer_support/ticket/{ticket_id}?success=Ticket assigned successfully"
            )

        except Exception as e:
            _logger.exception(f"Assign ticket error: {str(e)}")
            return werkzeug.utils.redirect(
                f"/customer_support/ticket/{ticket_id}?error=Error assigning ticket"
            )

    @http.route(
        "/customer_support/ticket/<int:ticket_id>/update_status",
        type="http",
        auth="user",
        methods=["POST"],
        website=True,
        csrf=True,
    )
    def update_ticket_status(self, ticket_id, **post):
        try:
            user = request.env.user
            ticket = request.env["customer.support"].browse(ticket_id)
            if not ticket.exists():
                return werkzeug.utils.redirect(
                    "/customer_support/dashboard?error=Ticket not found"
                )

            is_admin = user.has_group("base.group_system")
            is_assigned = (
                ticket.assigned_to.id == user.id if ticket.assigned_to else False
            )

            if not (is_admin or is_assigned):
                return werkzeug.utils.redirect(
                    f"/customer_support/ticket/{ticket_id}?error=Access denied"
                )

            # Normalize post data
            post_dict = dict(post) if not isinstance(post, dict) else post

            new_status = post_dict.get("status")
            if not new_status:
                return werkzeug.utils.redirect(
                    f"/customer_support/ticket/{ticket_id}?error=Status is required"
                )

            update_vals = {"state": new_status}

            if new_status == "resolved":
                update_vals["resolved_date"] = fields.Datetime.now()
            elif new_status == "closed":
                update_vals["closed_date"] = fields.Datetime.now()

            resolution_notes = post_dict.get("resolution_notes", "").strip()
            if resolution_notes:
                update_vals["resolution_notes"] = resolution_notes

            ticket.write(update_vals)

            _logger.info(f"Ticket {ticket.name} status updated to {new_status}")

            return werkzeug.utils.redirect(
                f"/customer_support/ticket/{ticket_id}?success=Status updated successfully"
            )

        except Exception as e:
            _logger.exception(f"Update status error: {str(e)}")
            return werkzeug.utils.redirect(
                f"/customer_support/ticket/{ticket_id}?error=Error updating status"
            )

    @http.route("/customer_support/logout", type="http", auth="user", website=True)
    def support_logout(self, **kw):
        try:
            request.session.logout()
            return werkzeug.utils.redirect("/customer_support")
        except Exception as e:
            _logger.error(f"Logout error: {str(e)}")
            return werkzeug.utils.redirect("/customer_support/login")

    @http.route(
        "/customer_support/admin_dashboard/users",
        type="http",
        auth="user",
        website=True,
    )
    def admin_users_list(self, **kw):
        """Admin user management page"""
        user = request.env.user
        if not user.has_group("base.group_system"):
            return werkzeug.utils.redirect("/customer_support/dashboard")

        # Get all users except admin and public user
        all_users = (
            request.env["res.users"]
            .search(
                [
                    ("id", "not in", [1, request.env.ref("base.public_user").id]),
                    ("active", "=", True),
                ]
            )
            .sorted(key=lambda r: r.create_date, reverse=True)
        )

        # Categorize users
        focal_persons = all_users.filtered(lambda u: u.has_group("base.group_user"))
        customers = all_users.filtered(
            lambda u: u.has_group("base.group_portal")
            and not u.has_group("base.group_user")
        )

        return request.render(
            "customer_support.admin_users_management",
            {
                "user": user,
                "focal_persons": focal_persons,
                "customers": customers,
                "page_name": "user_management",
                "success": kw.get("success", ""),
                "error": kw.get("error", ""),
                
            },
        )

    @http.route(
        "/customer_support/admin_dashboard/create_user",
        type="http",
        auth="user",
        website=True,
    )
    def admin_create_user_form(self, **kw):
        """Show create user form"""
        user = request.env.user
        if not user.has_group("base.group_system"):
            return werkzeug.utils.redirect("/customer_support/dashboard")

        return request.render(
            "customer_support.admin_create_user_form",
            {
                "user": user,
                "page_name": "create_user",
                "error": kw.get("error", ""),
            },
        )

    @http.route(
        "/customer_support/admin_dashboard/submit_user",
        type="http",
        auth="user",
        methods=["POST"],
        website=True,
        csrf=True,
    )
    def admin_submit_user(self, **post):
        """Handle user creation"""
        try:
            user = request.env.user
            if not user.has_group("base.group_system"):
                return werkzeug.utils.redirect("/customer_support/dashboard")

            # Normalize post data
            post_dict = dict(post) if not isinstance(post, dict) else post

            # Validate required fields
            name = post_dict.get("name", "").strip()
            email = post_dict.get("email", "").strip()
            password = post_dict.get("password", "").strip()
            user_type = post_dict.get("user_type", "customer")
            phone = post_dict.get("phone", "").strip()

            if not name:
                return werkzeug.utils.redirect(
                    "/customer_support/admin_dashboard/create_user?error=Name is required"
                )

            if not email:
                return werkzeug.utils.redirect(
                    "/customer_support/admin_dashboard/create_user?error=Email is required"
                )

            if not password:
                return werkzeug.utils.redirect(
                    "/customer_support/admin_dashboard/create_user?error=Password is required"
                )

            # Check if email already exists
            existing_user = (
                request.env["res.users"]
                .sudo()
                .search(["|", ("login", "=", email), ("email", "=", email)], limit=1)
            )

            if existing_user:
                return werkzeug.utils.redirect(
                    "/customer_support/admin_dashboard/create_user?error=Email already exists"
                )

            # Create partner first
            partner = (
                request.env["res.partner"]
                .sudo()
                .create(
                    {
                        "name": name,
                        "email": email,
                        "phone": phone,
                        "is_company": False,
                    }
                )
            )

            # Determine groups based on user type
            groups_to_add = []
            if user_type == "focal_person":
                # Internal user (employee) - can access backend and resolve tickets
                groups_to_add = [
                    request.env.ref("base.group_user").id,  # Internal User
                ]
            else:
                # Portal user (customer)
                groups_to_add = [
                    request.env.ref("base.group_portal").id,  # Portal User
                ]

            # Create user
            new_user = (
                request.env["res.users"]
                .sudo()
                .create(
                    {
                        "name": name,
                        "login": email,
                        "email": email,
                        "partner_id": partner.id,
                        "password": password,
                        "active": True,
                    }
                )
            )

            # Add groups to user
            if groups_to_add:
                new_user.sudo().write(
                    {
                        "group_ids": [(6, 0, groups_to_add)],
                    }
                )

            _logger.info(f"User created: {new_user.name} ({user_type}) by {user.name}")

            user_type_label = (
                "Focal Person" if user_type == "focal_person" else "Customer"
            )
            return werkzeug.utils.redirect(
                f"/customer_support/admin_dashboard/users?success={user_type_label} created successfully"
            )

        except Exception as e:
            _logger.exception(f"Create user error: {str(e)}")
            return werkzeug.utils.redirect(
                "/customer_support/admin_dashboard/create_user?error=Error creating user. Please try again."
            )

    @http.route(
        "/customer_support/admin_dashboard/user/<int:user_id>/edit",
        type="http",
        auth="user",
        website=True,
    )
    def admin_edit_user_form(self, user_id, **kw):
        """Show edit user form"""
        current_user = request.env.user
        if not current_user.has_group("base.group_system"):
            return werkzeug.utils.redirect("/customer_support/dashboard")

        edit_user = request.env["res.users"].sudo().browse(user_id)
        if not edit_user.exists():
            return werkzeug.utils.redirect(
                "/customer_support/admin_dashboard/users?error=User not found"
            )

        # Determine user type
        user_type = (
            "focal_person" if edit_user.has_group("base.group_user") else "customer"
        )

        return request.render(
            "customer_support.admin_edit_user_form",
            {
                "user": current_user,
                "edit_user": edit_user,
                "user_type": user_type,
                "page_name": "edit_user",
                "error": kw.get("error", ""),
            },
        )

    @http.route(
        "/customer_support/admin_dashboard/user/<int:user_id>/update",
        type="http",
        auth="user",
        methods=["POST"],
        website=True,
        csrf=True,
    )
    def admin_update_user(self, user_id, **post):
        """Handle user update"""
        try:
            current_user = request.env.user
            if not current_user.has_group("base.group_system"):
                return werkzeug.utils.redirect("/customer_support/dashboard")

            edit_user = request.env["res.users"].sudo().browse(user_id)
            if not edit_user.exists():
                return werkzeug.utils.redirect(
                    "/customer_support/admin_dashboard/users?error=User not found"
                )

            # Normalize post data
            post_dict = dict(post) if not isinstance(post, dict) else post

            # Validate required fields
            name = post_dict.get("name", "").strip()
            email = post_dict.get("email", "").strip()
            phone = post_dict.get("phone", "").strip()
            user_type = post_dict.get("user_type", "customer")
            password = post_dict.get("password", "").strip()

            if not name:
                return werkzeug.utils.redirect(
                    f"/customer_support/admin_dashboard/user/{user_id}/edit?error=Name is required"
                )

            if not email:
                return werkzeug.utils.redirect(
                    f"/customer_support/admin_dashboard/user/{user_id}/edit?error=Email is required"
                )

            # Check if email already exists (excluding current user)
            existing_user = (
                request.env["res.users"]
                .sudo()
                .search(
                    [
                        "|",
                        ("login", "=", email),
                        ("email", "=", email),
                        ("id", "!=", user_id),
                    ],
                    limit=1,
                )
            )

            if existing_user:
                return werkzeug.utils.redirect(
                    f"/customer_support/admin_dashboard/user/{user_id}/edit?error=Email already exists"
                )

            # Update partner
            edit_user.partner_id.sudo().write(
                {
                    "name": name,
                    "email": email,
                    "phone": phone,
                }
            )

            # Update user
            update_vals = {
                "name": name,
                "login": email,
                "email": email,
            }

            # Update password if provided
            if password:
                update_vals["password"] = password

            # Update groups based on user type
            if user_type == "focal_person":
                groups_to_add = [request.env.ref("base.group_user").id]
                groups_to_remove = [request.env.ref("base.group_portal").id]
            else:
                groups_to_add = [request.env.ref("base.group_portal").id]
                groups_to_remove = [request.env.ref("base.group_user").id]

            update_vals["groups_id"] = [
                (4, groups_to_add[0]),  # Add group
                (3, groups_to_remove[0]),  # Remove group
            ]

            edit_user.sudo().write(update_vals)

            _logger.info(f"User updated: {edit_user.name} by {current_user.name}")

            return werkzeug.utils.redirect(
                "/customer_support/admin_dashboard/users?success=User updated successfully"
            )

        except Exception as e:
            _logger.exception(f"Update user error: {str(e)}")
            return werkzeug.utils.redirect(
                f"/customer_support/admin_dashboard/user/{user_id}/edit?error=Error updating user"
            )

    @http.route(
        "/customer_support/admin_dashboard/user/<int:user_id>/toggle_active",
        type="http",
        auth="user",
        methods=["POST"],
        website=True,
        csrf=True,
    )
    def admin_toggle_user_active(self, user_id, **post):
        """Activate/Deactivate user"""
        try:
            current_user = request.env.user
            if not current_user.has_group("base.group_system"):
                return werkzeug.utils.redirect("/customer_support/dashboard")

            edit_user = request.env["res.users"].sudo().browse(user_id)
            if not edit_user.exists():
                return werkzeug.utils.redirect(
                    "/customer_support/admin_dashboard/users?error=User not found"
                )

            # Prevent deactivating self
            if edit_user.id == current_user.id:
                return werkzeug.utils.redirect(
                    "/customer_support/admin_dashboard/users?error=Cannot deactivate yourself"
                )

            new_status = not edit_user.active
            edit_user.sudo().write({"active": new_status})

            status_text = "activated" if new_status else "deactivated"
            _logger.info(f"User {status_text}: {edit_user.name} by {current_user.name}")

            return werkzeug.utils.redirect(
                f"/customer_support/admin_dashboard/users?success=User {status_text} successfully"
            )

        except Exception as e:
            _logger.exception(f"Toggle user active error: {str(e)}")
            return werkzeug.utils.redirect(
                "/customer_support/admin_dashboard/users?error=Error updating user status"
            )

    @http.route(
        "/customer_support/admin_dashboard/user/<int:user_id>/delete",
        type="http",
        auth="user",
        methods=["POST"],
        website=True,
        csrf=True,
    )
    def admin_delete_user(self, user_id, **post):
        """Delete user (archive)"""
        try:
            current_user = request.env.user
            if not current_user.has_group("base.group_system"):
                return werkzeug.utils.redirect("/customer_support/dashboard")

            edit_user = request.env["res.users"].sudo().browse(user_id)
            if not edit_user.exists():
                return werkzeug.utils.redirect(
                    "/customer_support/admin_dashboard/users?error=User not found"
                )

            # Prevent deleting self
            if edit_user.id == current_user.id:
                return werkzeug.utils.redirect(
                    "/customer_support/admin_dashboard/users?error=Cannot delete yourself"
                )

            user_name = edit_user.name

            # Archive user instead of delete
            edit_user.sudo().write({"active": False})

            _logger.info(f"User archived: {user_name} by {current_user.name}")

            return werkzeug.utils.redirect(
                "/customer_support/admin_dashboard/users?success=User deleted successfully"
            )

        except Exception as e:
            _logger.exception(f"Delete user error: {str(e)}")
            return werkzeug.utils.redirect(
                "/customer_support/admin_dashboard/users?error=Error deleting user"
            )

    @http.route("/customer_support/profile", type="http", auth="user", website=True)
    def display_profile(self, **kwargs):
        # This handles the initial page load and the redirect after saving
        return request.render(
            "customer_support.portal_profile_page",
            {
                "user": request.env.user,
                "error": kwargs.get("error"),
                "success": kwargs.get("success"),
            },
        )

    @http.route(
        "/customer_support/profile/update",
        type="http",
        auth="user",
        methods=["POST"],
        website=True,
    )
    def update_profile(self, **post):
        user = request.env.user

        # 1. Update Basic Info (Sudo needed if user has restricted portal access)
        user.sudo().write({"name": post.get("name")})
        user.partner_id.sudo().write({"phone": post.get("phone")})

        # 2. Check Password logic
        old_pwd = post.get("old_pwd")
        new_pwd = post.get("new_pwd")
        confirm_pwd = post.get("confirm_pwd")

        if old_pwd and new_pwd:
            if new_pwd != confirm_pwd:
                return request.render(
                    "customer_support.portal_profile_page",
                    {"user": user, "error": "New passwords do not match."},
                )

            try:
                # Odoo's built-in password change (handles hashing and verification)
                user.change_password(old_pwd, new_pwd)
            except Exception:
                return request.render(
                    "customer_support.portal_profile_page",
                    {"user": user, "error": "Incorrect current password."},
                )

        return request.redirect("/customer_support/profile?success=1")
        
    @http.route("/customer_support/logout_manual", type="http", auth="user", website=True)
    def logout_manual(self):
        # This manually clears the session so they are actually logged out
        request.session.logout() 
        return request.redirect("/customer_support/login")