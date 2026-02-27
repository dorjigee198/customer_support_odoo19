# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
import logging
import werkzeug

_logger = logging.getLogger(__name__)


class AdminTicketController(http.Controller):

    @http.route(
        ["/customer_support/admin_view/ticket/<int:ticket_id>"],
        type="http",
        auth="user",
        website=True,
    )
    def admin_ticket_detail_page(self, ticket_id, **kw):
        """
        DEDICATED ADMIN DETAIL VIEW
        - Fetches ticket and generates access tokens for attachments to prevent 404
        """
        try:
            # 1. Fetch the ticket record
            ticket = request.env["customer.support"].sudo().browse(ticket_id)

            if not ticket.exists():
                _logger.warning(
                    f"Admin tried to access non-existent ticket ID: {ticket_id}"
                )
                return request.render("website.404")

            # 2. Fetch attachments
            attachments = (
                request.env["ir.attachment"]
                .sudo()
                .search(
                    [("res_model", "=", "customer.support"), ("res_id", "=", ticket.id)]
                )
            )

            # 3. CRITICAL: Generate access tokens so the links don't 404
            for attach in attachments:
                if not attach.access_token:
                    attach.sudo().generate_access_token()

            _logger.info(
                f"Loading Admin Detail View for Ticket {ticket.id}. Files: {len(attachments)}"
            )

            # 4. Render the template
            return request.render(
                "customer_support.admin_ticket_detail",
                {
                    "ticket": ticket,
                    "attachments": attachments,
                },
            )

        except Exception as e:
            _logger.error(f"Admin detail route error for ticket {ticket_id}: {str(e)}")
            return request.redirect(
                "/customer_support/admin_dashboard?error=Could not load ticket details"
            )
