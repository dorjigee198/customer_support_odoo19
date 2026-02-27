import logging
from odoo import _
from odoo.http import request

_logger = logging.getLogger(__name__)


class EmailService:
    """Service class for handling all customer support emails"""

    @staticmethod
    def send_welcome_email(user_email, user_name, password):
        """
        Send welcome email to newly created customer account.

        Args:
            user_email (str): Customer's email address
            user_name (str): Customer's name
            password (str): Plain text password for initial login

        Returns:
            bool: True if email sent successfully, False otherwise
        """
        try:
            base_url = (
                request.env["ir.config_parameter"].sudo().get_param("web.base.url")
            )
            portal_login_link = f"{base_url}/customer_support/login"

            email_body = EmailService._get_welcome_email_template(
                user_name, user_email, password, portal_login_link
            )

            mail_values = {
                "subject": "Welcome to Customer Support Portal",
                "body_html": email_body,
                "email_to": user_email,
                "email_from": "kpowdyal@gmail.com",
                "auto_delete": False,
            }

            mail = request.env["mail.mail"].sudo().create(mail_values)
            mail.send()

            _logger.info(f"✓ Welcome email sent successfully to {user_email}")
            return True

        except Exception as e:
            _logger.error(f"✗ Failed to send welcome email to {user_email}: {str(e)}")
            return False

    @staticmethod
    def send_assignment_email(ticket, assigned_user):
        """
        Send assignment notification to support agent.

        Args:
            ticket: customer.support record
            assigned_user: res.users record

        Returns:
            bool: True if email sent successfully, False otherwise
        """
        try:
            agent_email = assigned_user.email or assigned_user.login
            if not agent_email:
                _logger.warning(f"✗ No email found for user {assigned_user.name}")
                return False

            base_url = (
                request.env["ir.config_parameter"].sudo().get_param("web.base.url")
            )
            ticket_url = f"{base_url}/customer_support/ticket/{ticket.id}"

            email_body = EmailService._get_assignment_email_template(
                ticket, assigned_user, ticket_url
            )

            mail_values = {
                "subject": f"New Ticket Assigned: {ticket.name} - {ticket.subject}",
                "body_html": email_body,
                "email_to": agent_email,
                "email_from": "kpowdyal@gmail.com",
                "auto_delete": False,
            }

            mail = request.env["mail.mail"].sudo().create(mail_values)
            mail.send()

            _logger.info(
                f"✓ Assignment email sent to {agent_email} for ticket {ticket.name}"
            )
            return True

        except Exception as e:
            _logger.error(
                f"✗ Failed to send assignment email for ticket {ticket.name}: {str(e)}"
            )
            return False

    @staticmethod
    def send_status_change_email(ticket, old_status, new_status):
        """
        Send status change notification to customer.

        Args:
            ticket: customer.support record
            old_status (str): Previous status
            new_status (str): New status

        Returns:
            bool: True if email sent successfully, False otherwise
        """
        try:
            # Skip certain statuses
            if new_status in ["new", "pending"]:
                _logger.info(
                    f"⊘ Skipping status email for {ticket.name}: status is '{new_status}'"
                )
                return True

            if new_status not in ["assigned", "in_progress", "resolved", "closed"]:
                _logger.info(
                    f"⊘ Skipping status email for {ticket.name}: '{new_status}' not in list"
                )
                return True

            customer_email = ticket.customer_id.email
            if not customer_email:
                _logger.warning(f"✗ No email for customer {ticket.customer_id.name}")
                return False

            base_url = (
                request.env["ir.config_parameter"].sudo().get_param("web.base.url")
            )
            ticket_url = f"{base_url}/customer_support/ticket/{ticket.id}"

            email_body = EmailService._get_status_change_email_template(
                ticket, old_status, new_status, ticket_url
            )

            mail_values = {
                "subject": f'Ticket Status Updated: {ticket.name} - {new_status.replace("_", " ").title()}',
                "body_html": email_body,
                "email_to": customer_email,
                "email_from": "kpowdyal@gmail.com",
                "auto_delete": False,
            }

            mail = request.env["mail.mail"].sudo().create(mail_values)
            mail.send()

            _logger.info(
                f"✓ Status email sent to {customer_email} for {ticket.name} ({old_status} → {new_status})"
            )
            return True

        except Exception as e:
            _logger.error(f"✗ Failed to send status email for {ticket.name}: {str(e)}")
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