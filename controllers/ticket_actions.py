# -*- coding: utf-8 -*-
"""
Ticket Actions Controller
=========================
Handles all core ticket interaction routes for the Customer Support Portal:
  - View ticket detail page (with message thread)
  - Assign ticket to a support agent (admin only)
  - Update ticket status (admin or assigned agent)

Customer notifications are created automatically on:
  - assign_ticket   → "assigned" notification
  - update_status   → "status_change" notification
"""

import json
import logging
from odoo import http, fields
from odoo.http import request
import werkzeug

from ..services.email_service import EmailService

_logger = logging.getLogger(__name__)

STATUS_LABELS = {
    "new": "New",
    "assigned": "Assigned",
    "in_progress": "In Progress",
    "pending": "Pending",
    "resolved": "Resolved",
    "closed": "Closed",
}


class CustomerSupportTicketActions(http.Controller):

    # =========================================================================
    # VIEW TICKET DETAIL
    # =========================================================================

    @http.route(
        "/customer_support/ticket/<int:ticket_id>",
        type="http",
        auth="user",
        website=True,
    )
    def view_ticket(self, ticket_id, **kw):
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

            activities = []
            try:
                if hasattr(ticket, "message_ids") and ticket.message_ids:
                    activities = list(
                        ticket.message_ids.filtered(
                            lambda m: m.message_type in ["comment", "notification"]
                        ).sorted(key=lambda r: r.date, reverse=True)
                    )
            except Exception as e:
                _logger.error(f"message_ids failed: {str(e)}")

            if not activities:
                try:
                    messages = (
                        request.env["mail.message"]
                        .sudo()
                        .search(
                            [
                                ("model", "=", "customer.support"),
                                ("res_id", "=", ticket_id),
                                ("message_type", "in", ["comment", "notification"]),
                            ],
                            order="date desc",
                        )
                    )
                    activities = list(messages)
                except Exception as e:
                    _logger.error(f"mail.message search failed: {str(e)}")

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

    # =========================================================================
    # ASSIGN TICKET
    # =========================================================================

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

            post_dict = dict(post) if not isinstance(post, dict) else post
            assigned_to = post_dict.get("assigned_to")
            if not assigned_to:
                return werkzeug.utils.redirect(
                    f"/customer_support/ticket/{ticket_id}?error=Please select a user to assign"
                )

            assigned_user_id = int(assigned_to)
            assigned_user = request.env["res.users"].browse(assigned_user_id)

            write_vals = {
                "assigned_to": assigned_user_id,
                "state": "assigned",
                "assigned_by": user.id,
                "assigned_date": fields.Datetime.now(),
            }

            # SLA Policy
            sla_policy_id = post_dict.get("sla_policy_id", "").strip()
            sla_note = ""
            if sla_policy_id:
                try:
                    policy = (
                        request.env["customer.support.sla.policy"]
                        .sudo()
                        .browse(int(sla_policy_id))
                    )
                    if policy.exists():
                        deadline = policy.get_deadline_from_now()
                        write_vals["sla_policy_id"] = policy.id
                        write_vals["sla_deadline"] = deadline
                        sla_note = f" | SLA: {policy.name} (due {deadline.strftime('%Y-%m-%d %H:%M')})"
                        _logger.info(
                            f"SLA policy '{policy.name}' attached to ticket {ticket_id}. Deadline: {deadline}"
                        )
                except Exception as sla_err:
                    _logger.warning(
                        f"Could not attach SLA policy to ticket {ticket_id}: {sla_err}"
                    )

            ticket.write(write_vals)
            _logger.info(
                f"Ticket {ticket.name} assigned to {assigned_user.name} by {user.name}{sla_note}"
            )

            ticket.message_post(
                body=f"Ticket assigned to {assigned_user.name}{sla_note}",
                subject="Ticket Assigned",
                partner_ids=[assigned_user.partner_id.id],
            )

            # Customer notification
            try:
                request.env["customer.support.notification"].create_notification(
                    ticket,
                    "assigned",
                    f"{ticket.name} has been assigned to {assigned_user.name}",
                )
            except Exception as ne:
                _logger.warning(f"Could not create assignment notification: {ne}")

            # Emails
            try:
                EmailService.send_assignment_email(ticket, assigned_user)
                EmailService.send_assignment_notification_to_customer(
                    ticket, assigned_user
                )
            except Exception as email_error:
                _logger.error(
                    f"Assignment email(s) failed for ticket {ticket.name}: {str(email_error)}"
                )

            return werkzeug.utils.redirect(
                f"/customer_support/admin_dashboard?tab=ticket-assignment"
                f"&success=Ticket {ticket.name} assigned successfully to {assigned_user.name}"
            )

        except Exception as e:
            _logger.exception(f"Assign ticket error: {str(e)}")
            return werkzeug.utils.redirect(
                f"/customer_support/ticket/{ticket_id}?error=Error assigning ticket"
            )

    # =========================================================================
    # UPDATE TICKET STATUS — csrf=False + JSON for kanban drag-drop
    # =========================================================================

    @http.route(
        "/customer_support/ticket/<int:ticket_id>/update_status",
        type="http",
        auth="user",
        methods=["POST"],
        website=True,
        csrf=False,
    )
    def update_ticket_status(self, ticket_id, **post):
        def _is_ajax():
            accept = request.httprequest.headers.get("Accept", "")
            x_req = request.httprequest.headers.get("X-Requested-With", "")
            return "application/json" in accept or x_req == "XMLHttpRequest"

        try:
            user = request.env.user
            ticket = request.env["customer.support"].browse(ticket_id)

            if not ticket.exists():
                if _is_ajax():
                    return request.make_response(
                        json.dumps({"success": False, "error": "Ticket not found"}),
                        headers=[("Content-Type", "application/json")],
                        status=404,
                    )
                return werkzeug.utils.redirect(
                    "/customer_support/dashboard?error=Ticket not found"
                )

            is_admin = user.has_group("base.group_system")
            is_assigned = (
                ticket.assigned_to.id == user.id if ticket.assigned_to else False
            )

            if not (is_admin or is_assigned):
                if _is_ajax():
                    return request.make_response(
                        json.dumps({"success": False, "error": "Access denied"}),
                        headers=[("Content-Type", "application/json")],
                        status=403,
                    )
                return werkzeug.utils.redirect(
                    f"/customer_support/ticket/{ticket_id}?error=Access denied"
                )

            post_dict = dict(post) if not isinstance(post, dict) else post
            new_status = post_dict.get("status")

            if not new_status:
                if _is_ajax():
                    return request.make_response(
                        json.dumps({"success": False, "error": "Status is required"}),
                        headers=[("Content-Type", "application/json")],
                        status=400,
                    )
                return werkzeug.utils.redirect(
                    f"/customer_support/ticket/{ticket_id}?error=Status is required"
                )

            old_status = ticket.state
            update_vals = {"state": new_status}

            if new_status == "resolved":
                update_vals["resolved_date"] = fields.Datetime.now()
            elif new_status == "closed":
                update_vals["closed_date"] = fields.Datetime.now()

            resolution_notes = post_dict.get("resolution_notes", "").strip()
            if resolution_notes:
                update_vals["resolution_notes"] = resolution_notes

            ticket.write(update_vals)
            _logger.info(
                f"Ticket {ticket.name} status: {old_status} → {new_status} by {user.name}"
            )

            # Customer notification
            try:
                old_label = STATUS_LABELS.get(old_status, old_status)
                new_label = STATUS_LABELS.get(new_status, new_status)
                focal_name = (
                    ticket.assigned_to.name if ticket.assigned_to else "Support Team"
                )
                notif_msg = (
                    f"{ticket.name} status changed from {old_label} "
                    f"to {new_label} by {focal_name}"
                )
                request.env["customer.support.notification"].create_notification(
                    ticket, "status_change", notif_msg
                )
            except Exception as ne:
                _logger.warning(f"Could not create status notification: {ne}")

            # Email
            try:
                EmailService.send_status_change_email(ticket, old_status, new_status)
            except Exception as email_error:
                _logger.error(
                    f"Status change email failed for ticket {ticket.name}: {str(email_error)}"
                )

            if _is_ajax():
                return request.make_response(
                    json.dumps(
                        {
                            "success": True,
                            "ticket_id": ticket_id,
                            "old_status": old_status,
                            "new_status": new_status,
                        }
                    ),
                    headers=[("Content-Type", "application/json")],
                )

            return werkzeug.utils.redirect(
                f"/customer_support/ticket/{ticket_id}?success=Status updated successfully"
            )

        except Exception as e:
            _logger.exception(f"Update status error: {str(e)}")
            if _is_ajax():
                return request.make_response(
                    json.dumps({"success": False, "error": str(e)}),
                    headers=[("Content-Type", "application/json")],
                    status=500,
                )
            return werkzeug.utils.redirect(
                f"/customer_support/ticket/{ticket_id}?error=Error updating status"
            )
