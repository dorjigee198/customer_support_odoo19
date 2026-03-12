# -*- coding: utf-8 -*-
"""
Support Agent (Focal Person) Dashboard Controller
==================================================
Handles the dashboard route for internal users (focal persons / support agents):
  - Displays tickets assigned to the logged-in agent
  - Shows ticket status counts and analytics
  - Redirects admins and customers to their own dashboards
  - Provides SLA alerts JSON endpoint for the bell notification dropdown

Access: Authenticated internal users (base.group_user).
Admins and portal users are redirected away automatically.
"""

import logging
import json
from odoo import http, fields
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
        Support Agent Dashboard - Main view for focal persons.
        Access: Authenticated internal users (focal persons)
        """
        try:
            user = request.env.user

            if user.id == request.env.ref("base.public_user").id:
                return werkzeug.utils.redirect(
                    "/customer_support/login?error=Please login to access dashboard"
                )

            if user.has_group("base.group_system"):
                return werkzeug.utils.redirect("/customer_support/admin_dashboard")

            if user.has_group("base.group_portal"):
                return werkzeug.utils.redirect("/customer_support/dashboard")

            tickets = (
                request.env["customer.support"]
                .sudo()
                .search([("assigned_to", "=", user.id)])
                .sorted(key=lambda r: r.create_date, reverse=True)
            )

            _logger.info(f"========== TICKETS FOR DASHBOARD ==========")
            _logger.info(f"User: {user.name} (ID: {user.id})")
            _logger.info(f"Found {len(tickets)} tickets")
            for t in tickets:
                _logger.info(
                    f"  - Ticket {t.id}: {t.name} | "
                    f"State: {t.state} | Priority: {t.priority}"
                )
            _logger.info(f"===========================================")

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

    # =========================================================================
    # SLA ALERTS — Bell notification endpoint
    # =========================================================================

    @http.route(
        "/customer_support/dashboard/sla_alerts",
        type="http",
        auth="user",
        website=True,
        csrf=False,
    )
    def sla_alerts(self, **kw):
        """
        Returns JSON list of SLA at-risk and breached tickets for the
        logged-in agent. Used by the bell notification dropdown in the
        support dashboard.

        SLA status is calculated LIVE from sla_deadline vs now —
        we do NOT rely on the stored sla_status field because it may
        not have been recomputed yet after deadline was set.

        At-risk threshold: less than 20% of total SLA time remaining
        OR less than 2 hours remaining — whichever comes first.
        """
        try:
            user = request.env.user
            now = fields.Datetime.now()

            # Fetch all open tickets assigned to this agent that have a deadline
            # No sla_status filter — we calculate it live below
            tickets = (
                request.env["customer.support"]
                .sudo()
                .search(
                    [
                        ("assigned_to", "=", user.id),
                        ("state", "not in", ["resolved", "closed"]),
                        ("sla_deadline", "!=", False),
                    ]
                )
            )

            alerts = []
            for ticket in tickets:
                remaining_seconds = (ticket.sla_deadline - now).total_seconds()

                # Calculate live SLA status
                if remaining_seconds <= 0:
                    # Already breached
                    live_status = "breached"
                elif remaining_seconds <= 2 * 3600:
                    # Less than 2 hours left → at risk
                    live_status = "at_risk"
                else:
                    # Check percentage remaining if we have assigned_date
                    if ticket.assigned_date and ticket.sla_deadline:
                        total_seconds = (
                            ticket.sla_deadline - ticket.assigned_date
                        ).total_seconds()
                        pct_remaining = (
                            (remaining_seconds / total_seconds * 100)
                            if total_seconds > 0
                            else 100
                        )
                        live_status = "at_risk" if pct_remaining <= 20 else "on_track"
                    else:
                        live_status = "on_track"

                # Only include at_risk and breached in the bell alerts
                if live_status not in ["at_risk", "breached"]:
                    continue

                # Build time display string
                if remaining_seconds <= 0:
                    over = abs(remaining_seconds)
                    h = int(over // 3600)
                    m = int((over % 3600) // 60)
                    time_display = (
                        f"{h}h {m}m past deadline" if h > 0 else f"{m}m past deadline"
                    )
                else:
                    h = int(remaining_seconds // 3600)
                    m = int((remaining_seconds % 3600) // 60)
                    time_display = (
                        f"{h}h {m}m remaining" if h > 0 else f"{m}m remaining"
                    )

                alerts.append(
                    {
                        "ticket_id": ticket.id,
                        "ticket_name": ticket.name,
                        "subject": ticket.subject or "(No subject)",
                        "sla_status": live_status,
                        "time_display": time_display,
                        "policy_name": (
                            ticket.sla_policy_id.name if ticket.sla_policy_id else "SLA"
                        ),
                    }
                )

                _logger.info(
                    f"SLA alert — {ticket.name} | status: {live_status} | "
                    f"deadline: {ticket.sla_deadline} | remaining: {remaining_seconds:.0f}s"
                )

            # Sort: breached first, then at_risk
            alerts.sort(key=lambda a: (0 if a["sla_status"] == "breached" else 1))

            _logger.info(f"SLA alerts for {user.name}: {len(alerts)} alerts")

            return request.make_response(
                json.dumps({"alerts": alerts}),
                headers={"Content-Type": "application/json"},
            )

        except Exception as e:
            _logger.error(f"SLA alerts error: {str(e)}")
            return request.make_response(
                json.dumps({"alerts": [], "error": str(e)}),
                headers={"Content-Type": "application/json"},
            )
