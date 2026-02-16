# controllers/tickets.py
from odoo import http
from odoo.http import request
import logging
import werkzeug

_logger = logging.getLogger(__name__)


class CustomerTickets(http.Controller):

    @http.route("/customer_support/tickets", type="http", auth="user", website=True)
    def customer_tickets(self, **kwargs):
        """
        Display all tickets created by the current customer
        """
        try:
            # Get current user's tickets
            user_id = request.env.user.id
            partner_id = request.env.user.partner_id.id

            # Search for tickets where customer_id matches the user's partner
            tickets = request.env["customer.support"].search(
                [("customer_id", "=", partner_id)], order="create_date desc"
            )

            # Prepare values for template
            values = {
                "user": request.env.user,
                "tickets": tickets,
                "ticket_count": len(tickets),
                "open_tickets": tickets.filtered(
                    lambda t: t.state not in ["resolved", "closed"]
                ),
                "resolved_tickets": tickets.filtered(
                    lambda t: t.state in ["resolved", "closed"]
                ),
            }

            return request.render("customer_support.customer_tickets", values)

        except Exception as e:
            _logger.error(f"Error loading tickets: {str(e)}")
            return request.redirect("/customer_support/dashboard")
    
    # ========== ADD THIS NEW ROUTE BELOW ==========
    
    @http.route(
        "/customer_support/customer/ticket/<int:ticket_id>",
        type="http",
        auth="user",
        website=True,
    )
    def customer_view_ticket(self, ticket_id, **kw):
        """
        Customer Ticket Details - Read-only view for customers
        Working: Shows ticket details with read-only interface for customers
        Access: Authenticated portal users (customers only)
        
        Customers can:
        - View ticket details
        - See communication history
        - Post messages
        
        Customers CANNOT:
        - Edit ticket status
        - Edit ticket priority
        - Assign tickets
        - Edit/delete messages
        """
        try:
            user = request.env.user
            
            # Check if user is logged in
            if user.id == request.env.ref("base.public_user").id:
                return werkzeug.utils.redirect(
                    "/customer_support/login?error=Please login"
                )

            # Get the ticket
            ticket = request.env["customer.support"].browse(ticket_id)
            if not ticket.exists():
                return werkzeug.utils.redirect(
                    "/customer_support/dashboard?error=Ticket not found"
                )

            # Security check: Customer can only view their own tickets
            is_customer = ticket.customer_id.id == user.partner_id.id
            is_admin = user.has_group("base.group_system")
            
            # If not the ticket owner and not admin, deny access
            if not is_customer and not is_admin:
                return werkzeug.utils.redirect(
                    "/customer_support/dashboard?error=You do not have permission to view this ticket"
                )

            # ============ RETRIEVE AND FILTER MESSAGES ============
            activities = []
            
            # Empty patterns to filter out
            empty_patterns = [
                '<p><br></p>', '<br>', '<p></p>', '<p><br/></p>',
                '<div><br></div>', '<p> </p>', '<p>\n</p>', '',
            ]

            try:
                if hasattr(ticket, "message_ids") and ticket.message_ids:
                    all_messages = ticket.sudo().message_ids.sorted(
                        key=lambda r: r.date, reverse=True
                    )
                    
                    # Filter out empty messages
                    filtered_messages = all_messages.filtered(
                        lambda m: (
                            m.body and
                            m.body.strip() and
                            m.body.strip() not in empty_patterns and
                            m.message_type in ['comment', 'notification'] and
                            len(m.body.strip()
                                .replace('<p>', '').replace('</p>', '')
                                .replace('<br>', '').replace('<br/>', '')
                                .replace('<div>', '').replace('</div>', '')
                                .strip()) > 0
                        )
                    )
                    
                    activities = list(filtered_messages)
                    
                    _logger.info(
                        f"Customer view - Ticket {ticket_id}: {len(all_messages)} total, "
                        f"{len(activities)} displayed after filtering"
                    )
                        
            except Exception as e:
                _logger.error(f"Message filtering error: {str(e)}")
                # Fallback to simple filtering
                try:
                    activities = list(
                        ticket.message_ids.filtered(
                            lambda m: m.message_type in ["comment", "notification"]
                        ).sorted(key=lambda r: r.date, reverse=True)
                    )
                except:
                    activities = []

            _logger.info(
                f"Customer {user.name} viewing ticket {ticket_id}: {len(activities)} messages"
            )

            # Render customer-specific template
            return request.render(
                "customer_support.customer_ticket_detail",
                {
                    "user": user,
                    "ticket": ticket,
                    "activities": activities,
                    "activities_count": len(activities),
                    "success": kw.get("success", ""),
                    "error": kw.get("error", ""),
                    "page_name": "ticket_detail",
                },
            )

        except Exception as e:
            _logger.error(f"Customer view ticket error: {str(e)}")
            import traceback
            _logger.error(f"Traceback: {traceback.format_exc()}")
            return werkzeug.utils.redirect(
                "/customer_support/dashboard?error=Error loading ticket"
            )
