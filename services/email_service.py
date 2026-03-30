# -*- coding: utf-8 -*-
"""
Email Service
=============
Coordinator for all customer support email notifications.
Template rendering is delegated to the email_templates package.
"""
import logging
from odoo.http import request
from .email_templates import (
    render_welcome_customer,
    render_welcome_agent,
    render_assignment_agent,
    render_assignment_customer,
    render_status_change,
)

_logger = logging.getLogger(__name__)


class EmailService:
    """Handles sending all customer support emails."""

    # ── Helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    def _get_default_email_from():
        try:
            mail_server = request.env["ir.mail_server"].sudo().search([], limit=1)
            if mail_server and mail_server.smtp_user:
                return mail_server.smtp_user
            default_from = (
                request.env["ir.config_parameter"].sudo().get_param("mail.default.from")
            )
            if default_from:
                return default_from
            return request.env.user.email or "noreply@example.com"
        except Exception as e:
            _logger.warning(f"Could not get default email: {e}, using fallback")
            return "noreply@example.com"

    @staticmethod
    def _get_base_url():
        base = request.env["ir.config_parameter"].sudo().get_param("web.base.url")
        return base.rstrip(
            "/"
        )  # ← FIXED: removes trailing slash to prevent double // in URLs

    @staticmethod
    def _send(subject, body_html, email_to):
        """Low-level send helper. Returns True on success."""
        mail = (
            request.env["mail.mail"]
            .sudo()
            .create(
                {
                    "subject": subject,
                    "body_html": body_html,
                    "email_to": email_to,
                    "email_from": EmailService._get_default_email_from(),
                    "auto_delete": False,
                }
            )
        )
        mail.send()
        return True

    # ── Public send methods ───────────────────────────────────────────────────

    @staticmethod
    def send_welcome_email(user_email, user_name, password):
        """Send welcome email to a newly created customer."""
        try:
            login_url = f"{EmailService._get_base_url()}/customer_support/login"
            body = render_welcome_customer(user_name, user_email, password, login_url)
            EmailService._send("Welcome to Customer Support Portal", body, user_email)
            _logger.info(f"✓ Welcome email sent to {user_email}")
            return True
        except Exception as e:
            _logger.error(f"✗ Welcome email failed for {user_email}: {e}")
            return False

    @staticmethod
    def send_welcome_email_focal_person(user_email, user_name, password):
        """Send welcome email to a newly created support agent."""
        try:
            login_url = f"{EmailService._get_base_url()}/customer_support/login"
            body = render_welcome_agent(user_name, user_email, password, login_url)
            EmailService._send(
                "Welcome to Customer Support Portal - Support Agent Account",
                body,
                user_email,
            )
            _logger.info(f"✓ Agent welcome email sent to {user_email}")
            return True
        except Exception as e:
            _logger.error(f"✗ Agent welcome email failed for {user_email}: {e}")
            return False

    @staticmethod
    def send_assignment_email(ticket, assigned_user):
        """Notify a support agent that a ticket was assigned to them."""
        try:
            agent_email = assigned_user.email or assigned_user.login
            if not agent_email:
                _logger.warning(f"✗ No email for user {assigned_user.name}")
                return False

            ticket_url = (
                f"{EmailService._get_base_url()}/customer_support/ticket/{ticket.id}"
            )
            body = render_assignment_agent(ticket, assigned_user, ticket_url)
            EmailService._send(
                f"New Ticket Assigned: {ticket.name} - {ticket.subject}",
                body,
                agent_email,
            )
            _logger.info(f"✓ Assignment email sent to {agent_email} for {ticket.name}")
            return True
        except Exception as e:
            _logger.error(f"✗ Assignment email failed for {ticket.name}: {e}")
            return False

    @staticmethod
    def send_assignment_notification_to_customer(ticket, assigned_user):
        """Notify the customer that their ticket has been assigned."""
        try:
            customer_email = ticket.customer_id.email
            if not customer_email:
                _logger.warning(f"✗ No email for customer {ticket.customer_id.name}")
                return False

            ticket_url = (
                f"{EmailService._get_base_url()}/customer_support/ticket/{ticket.id}"
            )
            body = render_assignment_customer(ticket, assigned_user, ticket_url)
            EmailService._send(
                f"Your Ticket Has Been Assigned: {ticket.name}",
                body,
                customer_email,
            )
            _logger.info(f"✓ Customer assignment notification sent to {customer_email}")
            return True
        except Exception as e:
            _logger.error(
                f"✗ Customer assignment notification failed for {ticket.name}: {e}"
            )
            return False

    @staticmethod
    def send_status_change_email(ticket, old_status, new_status):
        """Notify the customer of a ticket status change."""
        try:
            if new_status in ["new", "pending"]:
                return True
            if new_status not in ["assigned", "in_progress", "resolved", "closed"]:
                return True

            customer_email = ticket.customer_id.email
            if not customer_email:
                _logger.warning(f"✗ No email for customer {ticket.customer_id.name}")
                return False

            ticket_url = (
                f"{EmailService._get_base_url()}/customer_support/ticket/{ticket.id}"
            )
            body = render_status_change(ticket, old_status, new_status, ticket_url)
            EmailService._send(
                f"Ticket Status Updated: {ticket.name} - {new_status.replace('_', ' ').title()}",
                body,
                customer_email,
            )
            _logger.info(
                f"✓ Status email sent to {customer_email} ({old_status} → {new_status})"
            )
            return True
        except Exception as e:
            _logger.error(f"✗ Status email failed for {ticket.name}: {e}")
            return False
