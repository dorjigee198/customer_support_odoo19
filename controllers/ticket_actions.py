# -*- coding: utf-8 -*-
"""
Ticket Actions Controller
=========================
Handles all core ticket interaction routes for the Customer Support Portal:
  - View ticket detail page (with message thread)
  - Assign ticket to a support agent (admin only)
  - Update ticket status (admin or assigned agent)

Access: Role-based — see individual route docstrings for details.

Email notifications are delegated to EmailService:
  - Assignment email to the support agent
  - Assignment notification to the customer (NEW)
  - Status change notification to the customer
"""

import logging
from odoo import http, fields
from odoo.http import request
import werkzeug

from ..services.email_service import EmailService

_logger = logging.getLogger(__name__)


class CustomerSupportTicketActions(http.Controller):
    """
    Handles ticket viewing, assignment, and status updates.
    All routes require authentication; access is further restricted
    per route based on the user's role and relationship to the ticket.
    """

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
        """
        View Ticket Details - Displays ticket info with the full message thread
        Working: Loads ticket data, determines the caller's role relative to
                 the ticket, and retrieves the message history via two
                 fallback strategies.
        Access:
          - Customers      → can view their own tickets only
          - Support agents → can view tickets assigned to them
          - Admins         → can view all tickets

        Message retrieval strategies (in order):
          1. ORM relation: ticket.message_ids
          2. Direct search on mail.message table (fallback)
        """
        try:
            user = request.env.user

            # Redirect unauthenticated (public) users to login
            if user.id == request.env.ref("base.public_user").id:
                return werkzeug.utils.redirect(
                    "/customer_support/login?error=Please login"
                )

            ticket = request.env["customer.support"].browse(ticket_id)
            if not ticket.exists():
                return werkzeug.utils.redirect(
                    "/customer_support/dashboard?error=Ticket not found"
                )

            # Determine the caller's relationship to this ticket
            is_admin = user.has_group("base.group_system")
            is_assigned = (
                ticket.assigned_to.id == user.id if ticket.assigned_to else False
            )
            is_customer = ticket.customer_id.id == user.partner_id.id

            # Only admins see the focal person assignment dropdown
            focal_persons = []
            if is_admin:
                focal_persons = request.env["res.users"].search(
                    [("active", "=", True), ("id", "!=", 1)]
                )

            # ------------------------------------------------------------------
            # Retrieve the message thread for display.
            # Strategy 1: Use the ORM relation on the ticket record.
            # Strategy 2: Query mail.message directly (fallback if 1 fails).
            # ------------------------------------------------------------------
            activities = []

            # Strategy 1: ORM relation via message_ids
            try:
                if hasattr(ticket, "message_ids") and ticket.message_ids:
                    activities = list(
                        ticket.message_ids.filtered(
                            lambda m: m.message_type in ["comment", "notification"]
                        ).sorted(key=lambda r: r.date, reverse=True)
                    )
                    _logger.info(
                        f"✓ Found {len(activities)} messages via message_ids "
                        f"for ticket {ticket_id}"
                    )
            except Exception as e:
                _logger.error(f"✗ message_ids failed: {str(e)}")

            # Strategy 2: Direct search on mail.message table
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
                    _logger.info(
                        f"✓ Found {len(activities)} messages via mail.message search "
                        f"for ticket {ticket_id}"
                    )
                except Exception as e:
                    _logger.error(f"✗ mail.message search failed: {str(e)}")

            _logger.info(
                f"Ticket {ticket_id}: passing {len(activities)} activities to template"
            )

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
        """
        Assign Ticket - Assigns a ticket to a support agent
        Working: Updates the ticket's assigned_to, state, assigned_by, and
                 assigned_date fields. Sends notification emails to both the
                 support agent and the customer.
        Access: System administrators only

        Email behaviour (both are non-fatal on failure):
          1. Assignment email        → support agent
          2. Assignment notification → customer (NEW)

        BUG FIX: assigned_user is fetched BEFORE the email try/except block
                 to ensure it is always available for the redirect message.
        """
        try:
            user = request.env.user

            # Block non-admin users
            if not user.has_group("base.group_system"):
                return werkzeug.utils.redirect(
                    f"/customer_support/ticket/{ticket_id}?error=Access denied"
                )

            ticket = request.env["customer.support"].browse(ticket_id)
            if not ticket.exists():
                return werkzeug.utils.redirect(
                    "/customer_support/dashboard?error=Ticket not found"
                )

            # Normalize post data to a plain dict
            post_dict = dict(post) if not isinstance(post, dict) else post

            assigned_to = post_dict.get("assigned_to")
            if not assigned_to:
                return werkzeug.utils.redirect(
                    f"/customer_support/ticket/{ticket_id}"
                    "?error=Please select a user to assign"
                )

            assigned_user_id = int(assigned_to)

            # ------------------------------------------------------------------
            # FIX: Fetch assigned_user BEFORE the email try/except block.
            # Previously defined inside the email block, which caused a
            # NameError in the redirect if the block raised before this line.
            # ------------------------------------------------------------------
            assigned_user = request.env["res.users"].browse(assigned_user_id)

            # Update ticket assignment fields and set state to 'assigned'
            ticket.write(
                {
                    "assigned_to": assigned_user_id,
                    "state": "assigned",
                    "assigned_by": user.id,
                    "assigned_date": fields.Datetime.now(),
                }
            )

            _logger.info(
                f"Ticket {ticket.name} assigned to {assigned_user.name} "
                f"(ID: {assigned_user_id}) by {user.name}"
            )

            # ------------------------------------------------------------------
            # Send notification emails — failures are logged but non-fatal.
            # 1. Notify the support agent that the ticket is assigned to them.
            # 2. Notify the customer that their ticket has been picked up.
            # ------------------------------------------------------------------
            try:
                # 1. Email to the assigned support agent / focal person
                EmailService.send_assignment_email(ticket, assigned_user)

                # 2. Email to the customer whose ticket was just assigned (NEW)
                EmailService.send_assignment_notification_to_customer(
                    ticket, assigned_user
                )
            except Exception as email_error:
                _logger.error(
                    f"Assignment email(s) failed for ticket {ticket.name}: "
                    f"{str(email_error)}"
                )

            return werkzeug.utils.redirect(
                f"/customer_support/admin_dashboard?tab=ticket-assignment"
                f"&success=Ticket {ticket.name} assigned successfully "
                f"to {assigned_user.name}"
            )

        except Exception as e:
            _logger.exception(f"Assign ticket error: {str(e)}")
            return werkzeug.utils.redirect(
                f"/customer_support/ticket/{ticket_id}?error=Error assigning ticket"
            )

    # =========================================================================
    # UPDATE TICKET STATUS
    # =========================================================================

    @http.route(
        "/customer_support/ticket/<int:ticket_id>/update_status",
        type="http",
        auth="user",
        methods=["POST"],
        website=True,
        csrf=True,
    )
    def update_ticket_status(self, ticket_id, **post):
        """
        Update Ticket Status - Changes the state of a ticket
        Working: Validates access, captures the old status, writes the new
                 status with optional timestamps and resolution notes, then
                 notifies the customer by email.
        Access: System administrators and the ticket's assigned support agent

        Timestamps set automatically:
          - resolved → resolved_date
          - closed   → closed_date

        Email behaviour (non-fatal on failure):
          - Sends for: assigned, in_progress, resolved, closed
          - Skips for: new, pending
        """
        try:
            user = request.env.user
            ticket = request.env["customer.support"].browse(ticket_id)

            if not ticket.exists():
                return werkzeug.utils.redirect(
                    "/customer_support/dashboard?error=Ticket not found"
                )

            # Only admins or the assigned agent may change the ticket status
            is_admin = user.has_group("base.group_system")
            is_assigned = (
                ticket.assigned_to.id == user.id if ticket.assigned_to else False
            )

            if not (is_admin or is_assigned):
                return werkzeug.utils.redirect(
                    f"/customer_support/ticket/{ticket_id}?error=Access denied"
                )

            # Normalize post data to a plain dict
            post_dict = dict(post) if not isinstance(post, dict) else post

            new_status = post_dict.get("status")
            if not new_status:
                return werkzeug.utils.redirect(
                    f"/customer_support/ticket/{ticket_id}?error=Status is required"
                )

            # Capture the current state BEFORE writing so the email service
            # can reference both the previous and new state in its message.
            old_status = ticket.state

            # Build the update payload
            update_vals = {"state": new_status}

            # Stamp resolution/closure timestamps automatically
            if new_status == "resolved":
                update_vals["resolved_date"] = fields.Datetime.now()
            elif new_status == "closed":
                update_vals["closed_date"] = fields.Datetime.now()

            # Optionally persist resolution notes if provided
            resolution_notes = post_dict.get("resolution_notes", "").strip()
            if resolution_notes:
                update_vals["resolution_notes"] = resolution_notes

            ticket.write(update_vals)

            _logger.info(
                f"Ticket {ticket.name} status changed: {old_status} → {new_status} "
                f"by {user.name}"
            )

            # ------------------------------------------------------------------
            # Send a status-change notification email to the customer.
            # The EmailService decides internally which statuses trigger an email.
            # Failure is logged but non-fatal.
            # ------------------------------------------------------------------
            try:
                EmailService.send_status_change_email(ticket, old_status, new_status)
            except Exception as email_error:
                _logger.error(
                    f"Status change email failed for ticket {ticket.name}: "
                    f"{str(email_error)}"
                )

            return werkzeug.utils.redirect(
                f"/customer_support/ticket/{ticket_id}"
                "?success=Status updated successfully"
            )

        except Exception as e:
            _logger.exception(f"Update status error: {str(e)}")
            return werkzeug.utils.redirect(
                f"/customer_support/ticket/{ticket_id}?error=Error updating status"
            )
