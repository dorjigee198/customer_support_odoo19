
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
        return request.env["ir.config_parameter"].sudo().get_param("web.base.url")

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

    # Private template methods
    @staticmethod
    def _get_welcome_email_template(user_name, user_email, password, portal_login_link):
        """Returns HTML template for welcome email"""
        return f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #e0e0e0; border-radius: 8px;">
            <div style="background-color: #4CAF50; color: white; padding: 20px; border-radius: 8px 8px 0 0; text-align: center;">
                <h1 style="margin: 0; font-size: 24px;">Welcome to Customer Support Portal</h1>
            </div>
            
            <div style="padding: 30px; background-color: #f9f9f9;">
                <p style="font-size: 16px; color: #333;">Dear <strong>{user_name}</strong>,</p>
                
                <p style="font-size: 14px; color: #555; line-height: 1.6;">
                    Welcome to our Customer Support Portal! Your account has been created successfully.
                </p>
                
                <div style="background-color: white; padding: 20px; border-left: 4px solid #4CAF50; margin: 20px 0;">
                    <h3 style="margin-top: 0; color: #333;">Login Details:</h3>
                    <p style="margin: 5px 0; color: #555;"><strong>Email:</strong> {user_email}</p>
                    <p style="margin: 5px 0; color: #555;"><strong>Password:</strong> {password}</p>
                </div>
                
                <p style="font-size: 14px; color: #d32f2f; background-color: #ffebee; padding: 10px; border-radius: 4px;">
                    <strong>Important:</strong> Please log in and change your password for security.
                </p>
                
                <div style="text-align: center; margin: 30px 0;">
                    <a href="{portal_login_link}" 
                       style="background-color: #4CAF50; color: white; padding: 12px 30px; text-decoration: none; border-radius: 5px; font-weight: bold; display: inline-block;">
                        Access Portal
                    </a>
                </div>
                
                <p style="font-size: 14px; color: #555; line-height: 1.6;">
                    If you have any questions or need assistance, please don't hesitate to contact us.
                </p>
                
                <p style="font-size: 14px; color: #555; margin-top: 30px;">
                    Best regards,<br>
                    <strong>Customer Support Team</strong>
                </p>
            </div>
            
            <div style="background-color: #f0f0f0; padding: 15px; border-radius: 0 0 8px 8px; text-align: center; font-size: 12px; color: #888;">
                <p style="margin: 0;">This is an automated message. Please do not reply to this email.</p>
            </div>
        </div>
        """

    @staticmethod
    def _get_welcome_email_focal_person_template(
        user_name, user_email, password, portal_login_link
    ):
        """Returns HTML template for support agent welcome email"""
        return f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #e0e0e0; border-radius: 8px;">
            <div style="background-color: #2196F3; color: white; padding: 20px; border-radius: 8px 8px 0 0; text-align: center;">
                <h1 style="margin: 0; font-size: 24px;">Welcome to Customer Support Portal</h1>
                <p style="margin: 5px 0 0 0; font-size: 16px; opacity: 0.9;">Support Agent Account</p>
            </div>
            
            <div style="padding: 30px; background-color: #f9f9f9;">
                <p style="font-size: 16px; color: #333;">Dear <strong>{user_name}</strong>,</p>
                
                <p style="font-size: 14px; color: #555; line-height: 1.6;">
                    Welcome to our Customer Support Portal! Your <strong>Support Agent</strong> account has been created successfully.
                </p>
                
                <div style="background-color: white; padding: 20px; border-left: 4px solid #2196F3; margin: 20px 0;">
                    <h3 style="margin-top: 0; color: #333;">Login Details:</h3>
                    <p style="margin: 5px 0; color: #555;"><strong>Email:</strong> {user_email}</p>
                    <p style="margin: 5px 0; color: #555;"><strong>Password:</strong> {password}</p>
                    <p style="margin: 15px 0 5px 0; color: #555;"><strong>Role:</strong> Support Agent</p>
                </div>
                
                <div style="background-color: #e3f2fd; padding: 15px; border-radius: 4px; margin: 20px 0;">
                    <h3 style="margin-top: 0; color: #1976D2;">Your Responsibilities:</h3>
                    <ul style="margin: 10px 0; padding-left: 20px; color: #555;">
                        <li style="margin: 5px 0;">Review and respond to assigned support tickets</li>
                        <li style="margin: 5px 0;">Update ticket status as you work on issues</li>
                        <li style="margin: 5px 0;">Communicate with customers through ticket messages</li>
                        <li style="margin: 5px 0;">Resolve customer issues in a timely manner</li>
                    </ul>
                </div>
                
                <p style="font-size: 14px; color: #d32f2f; background-color: #ffebee; padding: 10px; border-radius: 4px;">
                    <strong>Security Notice:</strong> Please log in and change your password immediately for security purposes.
                </p>
                
                <div style="text-align: center; margin: 30px 0;">
                    <a href="{portal_login_link}" 
                       style="background-color: #2196F3; color: white; padding: 12px 30px; text-decoration: none; border-radius: 5px; font-weight: bold; display: inline-block;">
                        Access Support Dashboard
                    </a>
                </div>
                
                <p style="font-size: 14px; color: #555; line-height: 1.6;">
                    You will be redirected to your Support Dashboard after logging in, where you can view and manage assigned tickets.
                </p>
                
                <p style="font-size: 14px; color: #555; margin-top: 30px;">
                    Best regards,<br>
                    <strong>Customer Support Team</strong>
                </p>
            </div>
            
            <div style="background-color: #f0f0f0; padding: 15px; border-radius: 0 0 8px 8px; text-align: center; font-size: 12px; color: #888;">
                <p style="margin: 0;">This is an automated message. Please do not reply to this email.</p>
            </div>
        </div>
        """

    @staticmethod
    def _get_assignment_email_template(ticket, assigned_user, ticket_url):
        """Returns HTML template for assignment email"""
        priority_colors = {
            "low": "#4CAF50",
            "medium": "#FF9800",
            "high": "#FF5722",
            "urgent": "#D32F2F",
        }
        priority_color = priority_colors.get(ticket.priority, "#4CAF50")

        return f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #e0e0e0; border-radius: 8px;">
            <div style="background-color: #2196F3; color: white; padding: 20px; border-radius: 8px 8px 0 0;">
                <h1 style="margin: 0; font-size: 22px;">New Ticket Assigned: {ticket.name}</h1>
                <p style="margin: 5px 0 0 0; font-size: 14px; opacity: 0.9;">{ticket.subject}</p>
            </div>
            
            <div style="padding: 30px; background-color: #f9f9f9;">
                <p style="font-size: 16px; color: #333;">Dear <strong>{assigned_user.name}</strong>,</p>
                
                <p style="font-size: 14px; color: #555; line-height: 1.6;">
                    A new support ticket has been assigned to you. Please review and take action as needed.
                </p>
                
                <div style="background-color: white; padding: 20px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #2196F3;">
                    <h3 style="margin-top: 0; color: #333; border-bottom: 2px solid #e0e0e0; padding-bottom: 10px;">Ticket Details</h3>
                    
                    <table style="width: 100%; border-collapse: collapse;">
                        <tr>
                            <td style="padding: 8px 0; color: #777; font-weight: bold; width: 140px;">Ticket ID:</td>
                            <td style="padding: 8px 0; color: #333;">{ticket.name}</td>
                        </tr>
                        <tr>
                            <td style="padding: 8px 0; color: #777; font-weight: bold;">Subject:</td>
                            <td style="padding: 8px 0; color: #333;">{ticket.subject}</td>
                        </tr>
                        <tr>
                            <td style="padding: 8px 0; color: #777; font-weight: bold;">Customer:</td>
                            <td style="padding: 8px 0; color: #333;">{ticket.customer_id.name}</td>
                        </tr>
                        <tr>
                            <td style="padding: 8px 0; color: #777; font-weight: bold;">Priority:</td>
                            <td style="padding: 8px 0;">
                                <span style="background-color: {priority_color}; color: white; padding: 4px 12px; border-radius: 12px; font-size: 12px; font-weight: bold; text-transform: uppercase;">
                                    {ticket.priority}
                                </span>
                            </td>
                        </tr>
                    </table>
                    
                    <div style="margin-top: 15px; padding-top: 15px; border-top: 1px solid #e0e0e0;">
                        <p style="margin: 5px 0; color: #777; font-weight: bold;">Description:</p>
                        <p style="margin: 5px 0; color: #555; line-height: 1.6; background-color: #f5f5f5; padding: 10px; border-radius: 4px;">
                            {ticket.description}
                        </p>
                    </div>
                </div>
                
                <div style="text-align: center; margin: 30px 0;">
                    <a href="{ticket_url}" 
                       style="background-color: #2196F3; color: white; padding: 12px 30px; text-decoration: none; border-radius: 5px; font-weight: bold; display: inline-block;">
                        View Ticket
                    </a>
                </div>
                
                <p style="font-size: 14px; color: #555; margin-top: 30px;">
                    Best regards,<br>
                    <strong>Customer Support System</strong>
                </p>
            </div>
            
            <div style="background-color: #f0f0f0; padding: 15px; border-radius: 0 0 8px 8px; text-align: center; font-size: 12px; color: #888;">
                <p style="margin: 0;">This is an automated notification. Please do not reply to this email.</p>
            </div>
        </div>
        """

    @staticmethod
    def _get_assignment_notification_customer_template(
        ticket, assigned_user, ticket_url
    ):
        """Returns HTML template for customer assignment notification"""
        return f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #e0e0e0; border-radius: 8px;">
            <div style="background-color: #4CAF50; color: white; padding: 20px; border-radius: 8px 8px 0 0;">
                <h1 style="margin: 0; font-size: 22px;">Your Ticket Has Been Assigned</h1>
                <p style="margin: 5px 0 0 0; font-size: 14px; opacity: 0.9;">Ticket: {ticket.name}</p>
            </div>
            
            <div style="padding: 30px; background-color: #f9f9f9;">
                <p style="font-size: 16px; color: #333;">Dear <strong>{ticket.customer_id.name}</strong>,</p>
                
                <p style="font-size: 14px; color: #555; line-height: 1.6;">
                    Good news! Your ticket has been assigned to <strong>{assigned_user.name}</strong> who will assist you shortly.
                </p>
                
                <div style="background-color: #e8f5e9; padding: 20px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #4CAF50;">
                    <p style="font-size: 15px; color: #2e7d32; margin: 0; line-height: 1.6;">
                        <strong>✓ Your ticket is now being reviewed by our support team.</strong>
                    </p>
                </div>
                
                <div style="background-color: white; padding: 20px; border-radius: 8px; margin: 20px 0;">
                    <h3 style="margin-top: 0; color: #333; border-bottom: 2px solid #e0e0e0; padding-bottom: 10px;">Ticket Details</h3>
                    
                    <table style="width: 100%; border-collapse: collapse;">
                        <tr>
                            <td style="padding: 8px 0; color: #777; font-weight: bold; width: 140px;">Ticket ID:</td>
                            <td style="padding: 8px 0; color: #333;">{ticket.name}</td>
                        </tr>
                        <tr>
                            <td style="padding: 8px 0; color: #777; font-weight: bold;">Subject:</td>
                            <td style="padding: 8px 0; color: #333;">{ticket.subject}</td>
                        </tr>
                        <tr>
                            <td style="padding: 8px 0; color: #777; font-weight: bold;">Assigned To:</td>
                            <td style="padding: 8px 0; color: #333;"><strong>{assigned_user.name}</strong></td>
                        </tr>
                        <tr>
                            <td style="padding: 8px 0; color: #777; font-weight: bold;">Status:</td>
                            <td style="padding: 8px 0;">
                                <span style="background-color: #2196F3; color: white; padding: 4px 12px; border-radius: 12px; font-size: 12px; font-weight: bold; text-transform: uppercase;">
                                    ASSIGNED
                                </span>
                            </td>
                        </tr>
                    </table>
                </div>
                
                <div style="background-color: #fff3e0; padding: 15px; border-radius: 4px; margin: 20px 0; border-left: 3px solid #FF9800;">
                    <p style="margin: 0; color: #e65100; font-size: 14px;">
                        <strong>What happens next?</strong><br>
                        Our support agent will review your issue and start working on a solution. You'll receive updates as progress is made.
                    </p>
                </div>
                
                <div style="text-align: center; margin: 30px 0;">
                    <a href="{ticket_url}" 
                       style="background-color: #4CAF50; color: white; padding: 12px 30px; text-decoration: none; border-radius: 5px; font-weight: bold; display: inline-block;">
                        View Ticket Details
                    </a>
                </div>
                
                <p style="font-size: 14px; color: #555; line-height: 1.6;">
                    You can track the progress of your ticket and communicate with your support agent through the portal.
                </p>
                
                <p style="font-size: 14px; color: #555; margin-top: 30px;">
                    Best regards,<br>
                    <strong>Customer Support Team</strong>
                </p>
            </div>
            
            <div style="background-color: #f0f0f0; padding: 15px; border-radius: 0 0 8px 8px; text-align: center; font-size: 12px; color: #888;">
                <p style="margin: 0;">This is an automated notification. Please do not reply to this email.</p>
            </div>
        </div>
        """

    @staticmethod
    def _get_status_change_email_template(ticket, old_status, new_status, ticket_url):
        """Returns HTML template for status change email"""
        agent_name = (
            ticket.assigned_to.name if ticket.assigned_to else "our support team"
        )

        status_info = {
            "assigned": {
                "color": "#2196F3",
                "message": f"Your ticket has been acknowledged and assigned to {agent_name}. They will review it shortly.",
            },
            "in_progress": {
                "color": "#FF9800",
                "message": f"Good news! Our support team has started working on your ticket. {agent_name} is currently investigating and resolving your issue.",
            },
            "resolved": {
                "color": "#4CAF50",
                "message": f"Great news! Your support ticket has been resolved. {agent_name} has completed work on your issue. Please review the resolution.",
            },
            "closed": {
                "color": "#9E9E9E",
                "message": "Your support ticket has been closed. Thank you for using our support system.",
            },
        }

        status_details = status_info.get(
            new_status,
            {
                "color": "#2196F3",
                "message": f'Your ticket status has been updated to {new_status.replace("_", " ").title()}.',
            },
        )

        return f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #e0e0e0; border-radius: 8px;">
            <div style="background-color: {status_details['color']}; color: white; padding: 20px; border-radius: 8px 8px 0 0;">
                <h1 style="margin: 0; font-size: 22px;">Ticket Status Updated: {ticket.name}</h1>
                <p style="margin: 5px 0 0 0; font-size: 16px; opacity: 0.9;">
                    <strong>{new_status.replace('_', ' ').title()}</strong>
                </p>
            </div>
            
            <div style="padding: 30px; background-color: #f9f9f9;">
                <p style="font-size: 16px; color: #333;">Dear <strong>{ticket.customer_id.name}</strong>,</p>
                
                <p style="font-size: 14px; color: #555; line-height: 1.6;">
                    Your support ticket status has been updated.
                </p>
                
                <div style="background-color: {status_details['color']}15; padding: 20px; border-radius: 8px; margin: 20px 0; border-left: 4px solid {status_details['color']};">
                    <p style="font-size: 15px; color: #333; margin: 0; line-height: 1.6;">
                        <strong>{status_details['message']}</strong>
                    </p>
                </div>
                
                <div style="background-color: white; padding: 20px; border-radius: 8px; margin: 20px 0;">
                    <h3 style="margin-top: 0; color: #333; border-bottom: 2px solid #e0e0e0; padding-bottom: 10px;">Ticket Details</h3>
                    
                    <table style="width: 100%; border-collapse: collapse;">
                        <tr>
                            <td style="padding: 8px 0; color: #777; font-weight: bold; width: 140px;">Ticket ID:</td>
                            <td style="padding: 8px 0; color: #333;">{ticket.name}</td>
                        </tr>
                        <tr>
                            <td style="padding: 8px 0; color: #777; font-weight: bold;">Subject:</td>
                            <td style="padding: 8px 0; color: #333;">{ticket.subject}</td>
                        </tr>
                        <tr>
                            <td style="padding: 8px 0; color: #777; font-weight: bold;">Previous Status:</td>
                            <td style="padding: 8px 0; color: #666;">{old_status.replace('_', ' ').title()}</td>
                        </tr>
                        <tr>
                            <td style="padding: 8px 0; color: #777; font-weight: bold;">New Status:</td>
                            <td style="padding: 8px 0;">
                                <span style="background-color: {status_details['color']}; color: white; padding: 4px 12px; border-radius: 12px; font-size: 12px; font-weight: bold; text-transform: uppercase;">
                                    {new_status.replace('_', ' ')}
                                </span>
                            </td>
                        </tr>
                    </table>
                </div>
                
                <div style="text-align: center; margin: 30px 0;">
                    <a href="{ticket_url}" 
                       style="background-color: {status_details['color']}; color: white; padding: 12px 30px; text-decoration: none; border-radius: 5px; font-weight: bold; display: inline-block;">
                        View Ticket Details
                    </a>
                </div>
                
                <p style="font-size: 14px; color: #555; margin-top: 30px;">
                    Best regards,<br>
                    <strong>Customer Support Team</strong>
                </p>
            </div>
            
            <div style="background-color: #f0f0f0; padding: 15px; border-radius: 0 0 8px 8px; text-align: center; font-size: 12px; color: #888;">
                <p style="margin: 0;">This is an automated notification. Please do not reply to this email.</p>
            </div>
        </div>
        """