# controllers/support_dashboard.py
from odoo import http
from odoo.http import request
import werkzeug
from datetime import datetime, timedelta


class SupportDashboard(http.Controller):

    @http.route(
        "/customer_support/support_dashboard", type="http", auth="user", website=True
    )
    def support_dashboard(self, **kw):
        """
        Main dashboard route - YOUR ORIGINAL FUNCTIONALITY PRESERVED
        """
        # Ensure only focal persons can access
        if not request.env.user.has_group("base.group_user"):
            return werkzeug.utils.redirect(
                "/customer_support/login?error=Access Denied"
            )

        # Get tickets assigned to this user
        tickets = request.env["customer.support"].search(
            [("assigned_to", "=", request.env.user.id)]
        )

        # Get analytics data (NEW - for Overview page)
        analytics = self._get_analytics_data(request.env.user, tickets)

        # Get performance metrics (NEW - for My Performance card)
        performance = self._get_performance_metrics(request.env.user, tickets)

        # Render the dashboard template
        return request.render(
            "customer_support.focal_person",
            {
                "tickets": tickets,
                "user": request.env.user,
                "analytics": analytics,  # NEW
                "performance": performance,  # NEW
            },
        )

    # ============ NEW HELPER METHODS FOR ANALYTICS ============

    def _get_analytics_data(self, user, tickets):
        """
        Calculate analytics metrics for the Overview page
        """
        if not tickets:
            return {
                "open_tickets": 0,
                "total_tickets": 0,
                "high_priority": 0,
                "urgent": 0,
                "avg_open_hours": 0.0,
                "total_hours": 0.0,
                "avg_high_priority_hours": 0.0,
                "avg_urgent_hours": 0.0,
                "failed_tickets": 0,
                "failed_rate": 0.0,
                "high_priority_failed": 0,
                "urgent_failed": 0,
            }

        # Calculate open tickets (adjust field name if different in your model)
        # Assuming your model has a 'state' or 'stage_id' field
        try:
            open_tickets = len(tickets.filtered(lambda t: t.stage_id.is_close == False))
        except:
            # Fallback if stage_id doesn't exist
            open_tickets = len(
                tickets.filtered(lambda t: t.state not in ["closed", "done"])
            )

        # Count high priority and urgent tickets
        # Adjust priority values based on your model ('2' = High, '3' = Urgent)
        high_priority = len(tickets.filtered(lambda t: t.priority == "2"))
        urgent = len(tickets.filtered(lambda t: t.priority == "3"))

        # Calculate hours metrics
        avg_open_hours = self._calculate_avg_open_hours(tickets)
        total_hours = self._calculate_total_hours(tickets)
        avg_high_priority_hours = self._calculate_avg_priority_hours(tickets, "2")
        avg_urgent_hours = self._calculate_avg_priority_hours(tickets, "3")

        # Calculate failed tickets (adjust based on your model's failed state)
        try:
            failed_tickets = len(
                tickets.filtered(lambda t: t.stage_id.name in ["Failed", "Cancelled"])
            )
        except:
            failed_tickets = len(
                tickets.filtered(lambda t: t.state in ["failed", "cancelled"])
            )

        # Calculate failed rate
        failed_rate = (failed_tickets / len(tickets)) * 100 if len(tickets) > 0 else 0.0

        analytics = {
            "open_tickets": open_tickets,
            "total_tickets": len(tickets),
            "high_priority": high_priority,
            "urgent": urgent,
            "avg_open_hours": round(avg_open_hours, 2),
            "total_hours": round(total_hours, 2),
            "avg_high_priority_hours": round(avg_high_priority_hours, 2),
            "avg_urgent_hours": round(avg_urgent_hours, 2),
            "failed_tickets": failed_tickets,
            "failed_rate": round(failed_rate, 2),
            "high_priority_failed": len(
                tickets.filtered(
                    lambda t: t.priority == "2"
                    and (
                        hasattr(t.stage_id, "name")
                        and t.stage_id.name in ["Failed", "Cancelled"]
                    )
                )
            ),
            "urgent_failed": len(
                tickets.filtered(
                    lambda t: t.priority == "3"
                    and (
                        hasattr(t.stage_id, "name")
                        and t.stage_id.name in ["Failed", "Cancelled"]
                    )
                )
            ),
        }

        return analytics

    def _get_performance_metrics(self, user, tickets):
        """
        Calculate performance metrics for My Performance card
        """
        if not tickets:
            return {
                "today_closed": 0,
                "avg_last_7_days": 0.0,
                "daily_target": 80.00,
                "accuracy": 85.00,
            }

        today = datetime.now().date()
        week_ago = today - timedelta(days=7)

        # Today's closed tickets
        # Adjust the field name based on your model (close_date, date_closed, etc.)
        try:
            today_closed = len(
                tickets.filtered(
                    lambda t: hasattr(t, "close_date")
                    and t.close_date
                    and t.close_date.date() == today
                )
            )
        except:
            today_closed = 0

        # Last 7 days closed tickets
        try:
            last_7_days_closed = len(
                tickets.filtered(
                    lambda t: hasattr(t, "close_date")
                    and t.close_date
                    and t.close_date.date() >= week_ago
                )
            )
        except:
            last_7_days_closed = 0

        # Calculate average percentage
        avg_last_7_days = (
            (last_7_days_closed / 7) * 100 if last_7_days_closed > 0 else 0
        )

        # You can make these configurable in settings
        daily_target = 80.00
        accuracy = 85.00

        performance = {
            "today_closed": today_closed,
            "avg_last_7_days": round(avg_last_7_days, 2),
            "daily_target": daily_target,
            "accuracy": accuracy,
        }

        return performance

    def _calculate_avg_open_hours(self, tickets):
        """
        Calculate average hours tickets have been open
        """
        if not tickets:
            return 0.0

        try:
            open_tickets = tickets.filtered(lambda t: t.stage_id.is_close == False)
        except:
            open_tickets = tickets.filtered(lambda t: t.state not in ["closed", "done"])

        if not open_tickets:
            return 0.0

        total_hours = 0
        for ticket in open_tickets:
            if ticket.create_date:
                delta = datetime.now() - ticket.create_date
                total_hours += delta.total_seconds() / 3600

        return total_hours / len(open_tickets) if open_tickets else 0.0

    def _calculate_total_hours(self, tickets):
        """
        Calculate total hours spent on all tickets
        """
        if not tickets:
            a
        return 0.0

        total_hours = 0
        for ticket in tickets:
            if ticket.create_date:
                try:
                    end_date = ticket.close_date or datetime.now()
                except:
                    end_date = datetime.now()

                delta = end_date - ticket.create_date
                total_hours += delta.total_seconds() / 3600

        return total_hours

    def _calculate_avg_priority_hours(self, tickets, priority):
        """
        Calculate average hours for specific priority tickets
        """
        if not tickets:
            return 0.0

        priority_tickets = tickets.filtered(lambda t: t.priority == priority)

        if not priority_tickets:
            return 0.0

        total_hours = 0
        for ticket in priority_tickets:
            if ticket.create_date:
                try:
                    end_date = ticket.close_date or datetime.now()
                except:
                    end_date = datetime.now()

                delta = end_date - ticket.create_date
                total_hours += delta.total_seconds() / 3600

        return total_hours / len(priority_tickets)

    # ============ NEW AJAX ENDPOINT FOR SEARCH ============

    @http.route("/customer_support/tickets/search", type="json", auth="user")
    def search_tickets(self, search_term="", **kwargs):
        """
        AJAX endpoint for searching tickets (for search bar functionality)
        """
        user = request.env.user

        # Base domain - same as your original
        domain = [("assigned_to", "=", user.id)]

        # Add search filter if provided
        if search_term:
            domain += [
                "|",
                ("name", "ilike", search_term),
                ("subject", "ilike", search_term),
            ]

        tickets = request.env["customer.support"].search(
            domain, order="create_date desc"
        )

        # Return ticket data as JSON
        tickets_data = []
        for ticket in tickets:
            try:
                customer_name = (
                    ticket.partner_id.name if ticket.partner_id else "Unknown"
                )
            except:
                customer_name = "Unknown"

            try:
                status = ticket.stage_id.name if ticket.stage_id else ticket.state
            except:
                status = "New"

            try:
                created = (
                    ticket.create_date.strftime("%b %d, %I:%M %p")
                    if ticket.create_date
                    else ""
                )
            except:
                created = ""

            try:
                project = ticket.team_id.name if ticket.team_id else ""
            except:
                project = ""

            tickets_data.append(
                {
                    "id": ticket.id,
                    "name": ticket.name,
                    "subject": (
                        ticket.subject if hasattr(ticket, "subject") else ticket.name
                    ),
                    "state": status,
                    "priority": ticket.priority if hasattr(ticket, "priority") else "1",
                    "customer": customer_name,
                    "created": created,
                    "project": project,
                }
            )

        return {"tickets": tickets_data, "count": len(tickets_data)}
