# -*- coding: utf-8 -*-
"""
Support Agent (Focal Person) Dashboard Controller
==================================================
Handles the dashboard route for internal users (focal persons / support agents):
  - Displays tickets assigned to the logged-in agent
  - Shows ticket status counts and analytics
  - Redirects admins and customers to their own dashboards

Access: Authenticated internal users (base.group_user).
Admins and portal users are redirected away automatically.
"""

import logging
from odoo import http
from odoo.http import request
import werkzeug

_logger = logging.getLogger(__name__)


class CustomerSupportAgent(http.Controller):
    """
    Handles the support agent (focal person) dashboard.
    Only internal users reach this view — admins and customers
    are redirected to their respective dashboards.
    """

    # =========================================================================
    # SUPPORT AGENT DASHBOARD
    # =========================================================================

    @http.route(
        "/customer_support/support_dashboard", type="http", auth="user", website=True
    )
    def support_agent_dashboard(self, **kw):
        """
        Support Agent Dashboard - Main view for focal persons
        Working: Shows all tickets assigned to the logged-in agent,
                 status counts, analytics, and performance metrics.
        Access: Authenticated internal users (focal persons)

        Redirects:
          - Public (unauthenticated) users → login
          - Admin users                   → /customer_support/admin_dashboard
          - Portal users (customers)      → /customer_support/dashboard
        """
        try:
            user = request.env.user

            # Redirect unauthenticated (public) users to login
            if user.id == request.env.ref("base.public_user").id:
                return werkzeug.utils.redirect(
                    "/customer_support/login?error=Please login to access dashboard"
                )

            # Admins should not land here — send them to the admin dashboard
            if user.has_group("base.group_system"):
                return werkzeug.utils.redirect("/customer_support/admin_dashboard")

            # Portal users (customers) should go to the customer dashboard
            if user.has_group("base.group_portal"):
                return werkzeug.utils.redirect("/customer_support/dashboard")

            # Fetch only tickets assigned to this specific agent, newest first
            tickets = (
                request.env["customer.support"]
                .sudo()
                .search([("assigned_to", "=", user.id)])
                .sorted(key=lambda r: r.create_date, reverse=True)
            )

            # Debug logging — visible in the Odoo server log for troubleshooting
            _logger.info(f"========== TICKETS FOR DASHBOARD ==========")
            _logger.info(f"User: {user.name} (ID: {user.id})")
            _logger.info(f"Found {len(tickets)} tickets")
            for t in tickets:
                _logger.info(
                    f"  - Ticket {t.id}: {t.name} | "
                    f"State: {t.state} | Priority: {t.priority}"
                )
            _logger.info(f"===========================================")

            # Build a count summary per ticket status for the stat cards
            ticket_counts = {
                "new": len(tickets.filtered(lambda t: t.state == "new")),
                "assigned": len(tickets.filtered(lambda t: t.state == "assigned")),
                "in_progress": len(
                    tickets.filtered(lambda t: t.state == "in_progress")
                ),
                "resolved": len(tickets.filtered(lambda t: t.state == "resolved")),
                "closed": len(tickets.filtered(lambda t: t.state == "closed")),
                "total": len(tickets),
            }

            # Attempt to load advanced analytics from the dashboard model.
            # Falls back to safe defaults if the model is unavailable.
            analytics = {}
            performance = {}
            try:
                dashboard_model = request.env["customer_support.dashboard"]
                analytics = dashboard_model.get_ticket_analytics(user.id)
                performance = dashboard_model.get_user_performance(user.id)
            except Exception as e:
                _logger.warning(f"Support dashboard analytics failed: {str(e)}")
                open_tickets = (
                    ticket_counts.get("new", 0)
                    + ticket_counts.get("assigned", 0)
                    + ticket_counts.get("in_progress", 0)
                )
                # Safe defaults so the template never throws a KeyError
                analytics = {
                    "open_tickets": open_tickets,
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
                "customer_support.support_agent_dashboard",
                {
                    "user": user,
                    "tickets": tickets,
                    "ticket_counts": ticket_counts,
                    "analytics": analytics,
                    "performance": performance,
                    "page_name": "support_dashboard",
                },
            )

        except Exception as e:
            _logger.error(f"Support dashboard error: {str(e)}")
            return werkzeug.utils.redirect(
                "/customer_support/login?error=Error loading support dashboard"
            )
