# models/dashboard.py
from odoo import models, fields, api
from datetime import datetime, timedelta


class CustomerSupportProject(models.Model):
    _name = "customer_support.project"
    _description = "Support Project"

    name = fields.Char(string="Project Name", required=True)
    code = fields.Char(string="Project Code")
    description = fields.Text(string="Description")
    active = fields.Boolean(string="Active", default=True)


# ============ ADD THIS CLASS HERE ============
class ResPartner(models.Model):
    """Extend res.partner to add project association"""

    _inherit = "res.partner"

    project_id = fields.Many2one(
        "customer_support.project",
        string="Project",
        help="The project this user/partner is associated with",
    )


# ============ END OF NEW CLASS ============


class CustomerSupportDashboard(models.AbstractModel):
    _name = "customer_support.dashboard"
    _description = "Customer Support Dashboard Analytics"

    def get_ticket_analytics(self, user_id):
        """Get ticket analytics for dashboard"""
        try:
            Ticket = self.env["customer.support"]
            user = self.env["res.users"].browse(user_id)

            # Get all tickets for the user (created by them or assigned to their customer)
            tickets = Ticket.search([("customer_id", "=", user.partner_id.id)])

            total_tickets = len(tickets)

            # Filter by status
            open_tickets = tickets.filtered(
                lambda t: t.state in ["new", "in_progress", "pending"]
            )
            high_priority = tickets.filtered(
                lambda t: t.priority == "high"
                and t.state in ["new", "in_progress", "pending"]
            )
            urgent_tickets = tickets.filtered(
                lambda t: t.priority == "urgent"
                and t.state in ["new", "in_progress", "pending"]
            )

            # Resolved/Closed tickets
            resolved_tickets = tickets.filtered(
                lambda t: t.state in ["resolved", "closed"]
            )
            high_resolved = resolved_tickets.filtered(lambda t: t.priority == "high")
            urgent_resolved = resolved_tickets.filtered(
                lambda t: t.priority == "urgent"
            )

            # Calculate solve rate
            solve_rate = (
                (len(resolved_tickets) / total_tickets * 100)
                if total_tickets > 0
                else 0
            )

            return {
                "total_tickets": total_tickets,
                "open_tickets": len(open_tickets),
                "high_priority": len(high_priority),
                "urgent": len(urgent_tickets),
                "avg_open_hours": 0,
                "total_hours": 0,
                "avg_high_hours": 0,
                "avg_urgent_hours": 0,
                "resolved_tickets": len(resolved_tickets),
                "solve_rate": round(solve_rate, 2),
                "high_resolved": len(high_resolved),
                "urgent_resolved": len(urgent_resolved),
            }
        except Exception as e:
            # Log error
            self.env["ir.logging"].sudo().create(
                {
                    "name": "Dashboard Analytics Error",
                    "type": "server",
                    "path": "dashboard.py",
                    "func": "get_ticket_analytics",
                    "line": 1,
                    "message": f"Error getting ticket analytics: {str(e)}",
                }
            )
            return {}

    def get_user_performance(self, user_id):
        """Get user performance metrics"""
        try:
            Ticket = self.env["customer.support"]

            # Today's resolved/closed tickets
            today = fields.Date.today()
            today_start = datetime.combine(today, datetime.min.time())
            today_end = datetime.combine(today, datetime.max.time())

            today_closed = Ticket.search_count(
                [
                    ("assigned_to", "=", user_id),
                    ("state", "in", ["resolved", "closed"]),
                    ("resolved_date", ">=", today_start),
                    ("resolved_date", "<=", today_end),
                ]
            )

            # Last 7 days average
            seven_days_ago = today - timedelta(days=7)
            last_week_tickets = Ticket.search(
                [
                    ("assigned_to", "=", user_id),
                    ("create_date", ">=", seven_days_ago),
                    ("create_date", "<=", today_end),
                ]
            )

            resolved_last_week = last_week_tickets.filtered(
                lambda t: t.state in ["resolved", "closed"]
            )
            avg_resolve_rate = (
                (len(resolved_last_week) / len(last_week_tickets) * 100)
                if len(last_week_tickets) > 0
                else 0
            )

            return {
                "today_closed": today_closed,
                "avg_resolve_rate": round(avg_resolve_rate, 2),
                "daily_target": 80.00,
                "achievement": (
                    round((today_closed / 5 * 100), 2) if today_closed > 0 else 0
                ),
                "sample_performance": 85.00,
            }
        except Exception as e:
            # Log error
            self.env["ir.logging"].sudo().create(
                {
                    "name": "Dashboard Performance Error",
                    "type": "server",
                    "path": "dashboard.py",
                    "func": "get_user_performance",
                    "line": 1,
                    "message": f"Error getting user performance: {str(e)}",
                }
            )
            return {}
