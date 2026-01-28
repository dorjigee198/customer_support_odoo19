# controllers/tickets.py
from odoo import http
from odoo.http import request
import logging

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
