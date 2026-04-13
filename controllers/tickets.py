from odoo import http
from odoo.http import request
import logging
import werkzeug

_logger = logging.getLogger(__name__)  # fixed: was logger = logging.getLogger(name_)


class CustomerTickets(http.Controller):

    @http.route("/customer_support/tickets", type="http", auth="user", website=True)
    def customer_tickets(self, **kwargs):
        """Redirect list view to kanban — kanban is the primary customer view."""
        return werkzeug.utils.redirect("/customer_support/tickets/list")

    @http.route("/customer_support/tickets/list", type="http", auth="user", website=True)
    def customer_tickets_list(self, **kwargs):
        """
        List view of customer tickets (accessible via /tickets/list).
        """
        try:
            partner_id = request.env.user.partner_id.id
            tickets = request.env["customer.support"].search(
                [("customer_id", "=", partner_id)], order="create_date desc"
            )
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
            _logger.error(f"Error loading tickets list: {str(e)}")
            return werkzeug.utils.redirect("/customer_support/dashboard")

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
                "<p><br></p>",
                "<br>",
                "<p></p>",
                "<p><br/></p>",
                "<div><br></div>",
                "<p> </p>",
                "<p>\n</p>",
                "",
            ]

            try:
                if hasattr(ticket, "message_ids") and ticket.message_ids:
                    all_messages = ticket.sudo().message_ids.sorted(
                        key=lambda r: r.date, reverse=True
                    )

                    # Filter out empty messages
                    filtered_messages = all_messages.filtered(
                        lambda m: (
                            m.body
                            and m.body.strip()
                            and m.body.strip() not in empty_patterns
                            and m.message_type in ["comment", "notification"]
                            and len(
                                m.body.strip()
                                .replace("<p>", "")
                                .replace("</p>", "")
                                .replace("<br>", "")
                                .replace("<br/>", "")
                                .replace("<div>", "")
                                .replace("</div>", "")
                                .strip()
                            )
                            > 0
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
                except Exception:
                    activities = []

            _logger.info(
                f"Customer {user.name} viewing ticket {ticket_id}: {len(activities)} messages"
            )

            # Load board columns and tasks (read-only view for the customer)
            board_columns = []
            board_total = 0
            board_done = 0
            try:
                columns = (
                    request.env["customer_support.ticket.column"]
                    .sudo()
                    .search([("ticket_id", "=", ticket_id)], order="sequence, id")
                )
                for col in columns:
                    tasks = []
                    for task in col.task_ids.sorted(key=lambda t: (t.sequence, t.id)):
                        tasks.append({
                            "name": task.name,
                            "is_done": task.is_done,
                            "members": [
                                {"name": m.name,
                                 "initials": "".join(p[0].upper() for p in m.name.split()[:2])}
                                for m in task.member_ids
                            ],
                        })
                        board_total += 1
                        if task.is_done:
                            board_done += 1
                    board_columns.append({
                        "name": col.name,
                        "color": col.color or "#e2e8f0",
                        "tasks": tasks,
                        "task_count": len(tasks),
                        "done_count": sum(1 for t in tasks if t["is_done"]),
                    })
            except Exception as e:
                _logger.error(f"Board columns load error: {str(e)}")

            board_progress = int(board_done / board_total * 100) if board_total > 0 else 0

            # Render customer-specific template
            response = request.render(
                "customer_support.customer_ticket_detail",
                {
                    "user": user,
                    "ticket": ticket,
                    "activities": activities,
                    "activities_count": len(activities),
                    "board_columns": board_columns,
                    "board_total": board_total,
                    "board_done": board_done,
                    "board_progress": board_progress,
                    "success": kw.get("success", ""),
                    "error": kw.get("error", ""),
                    "page_name": "ticket_detail",
                },
            )
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            return response

        except Exception as e:
            _logger.error(f"Customer view ticket error: {str(e)}")
            import traceback

            _logger.error(f"Traceback: {traceback.format_exc()}")
            return werkzeug.utils.redirect(
                "/customer_support/dashboard?error=Error loading ticket"
            )

    @http.route(
        "/customer_support/customer/ticket/<int:ticket_id>/data",
        type="json", auth="user", csrf=False,
    )
    def customer_ticket_data(self, ticket_id, **kw):
        """JSON endpoint — returns ticket detail data for the modal popup."""
        try:
            user = request.env.user
            ticket = request.env["customer.support"].sudo().browse(ticket_id)
            if not ticket.exists():
                return {"error": "Ticket not found"}
            if ticket.customer_id.id != user.partner_id.id and not user.has_group("base.group_system"):
                return {"error": "Access denied"}

            # Board columns + tasks
            board_columns = []
            board_total = board_done = 0
            columns = request.env["customer_support.ticket.column"].sudo().search(
                [("ticket_id", "=", ticket_id)], order="sequence, id"
            )
            for col in columns:
                tasks = []
                for task in col.task_ids.sorted(key=lambda t: (t.sequence, t.id)):
                    tasks.append({"name": task.name, "is_done": task.is_done})
                    board_total += 1
                    if task.is_done:
                        board_done += 1
                board_columns.append({
                    "name": col.name,
                    "color": col.color or "#e2e8f0",
                    "tasks": tasks,
                    "task_count": len(tasks),
                    "done_count": sum(1 for t in tasks if t["is_done"]),
                })

            board_progress = int(board_done / board_total * 100) if board_total > 0 else 0

            # Last 8 messages
            messages = []
            try:
                msgs = request.env["mail.message"].sudo().search(
                    [("model", "=", "customer.support"), ("res_id", "=", ticket_id),
                     ("message_type", "in", ["comment", "notification"])],
                    order="date desc", limit=8,
                )
                for m in msgs:
                    if not m.body or not m.body.strip() or m.body.strip() in ["<p><br></p>", "<p></p>"]:
                        continue
                    messages.append({
                        "author": m.author_id.name if m.author_id else "System",
                        "date": m.date.strftime("%b %d, %Y %H:%M") if m.date else "",
                        "body": m.body or "",
                    })
            except Exception:
                pass

            state_labels = {
                "new": "New", "assigned": "Assigned", "in_progress": "In Progress",
                "pending": "Pending", "resolved": "Resolved", "closed": "Closed",
            }

            return {
                "success": True,
                "ticket": {
                    "id": ticket.id,
                    "name": ticket.name,
                    "subject": ticket.subject,
                    "state": ticket.state,
                    "state_label": state_labels.get(ticket.state, ticket.state),
                    "priority": ticket.priority or "medium",
                    "description": ticket.description or "",
                    "created": ticket.create_date.strftime("%b %d, %Y") if ticket.create_date else "",
                    "assigned_to": ticket.assigned_to.name if ticket.assigned_to else "Unassigned",
                    "sla_status": ticket.sla_status or "none",
                    "sla_deadline": ticket.sla_deadline.strftime("%b %d, %Y") if ticket.sla_deadline else "",
                },
                "board_columns": board_columns,
                "board_total": board_total,
                "board_done": board_done,
                "board_progress": board_progress,
                "messages": messages,
            }
        except Exception as e:
            _logger.error(f"ticket_data error: {e}")
            return {"error": str(e)}

    @http.route(
        "/customer_support/tickets/states",
        type="json", auth="user", csrf=False,
    )
    def customer_tickets_states(self, **kw):
        """Returns current {ticket_id: state} map for the logged-in customer — used by kanban polling."""
        try:
            user = request.env.user
            tickets = request.env["customer.support"].sudo().search(
                [("customer_id", "=", user.partner_id.id)]
            )
            state_labels = {
                "new": "New", "assigned": "Assigned", "in_progress": "In Progress",
                "pending": "Pending", "resolved": "Resolved", "closed": "Closed",
            }
            return {
                "success": True,
                "states": {
                    str(t.id): {"state": t.state, "label": state_labels.get(t.state, t.state)}
                    for t in tickets
                },
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    @http.route(
        "/customer_support/tickets/kanban", type="http", auth="user", website=True
    )
    def customer_tickets_kanban(self, **kw):
        """
        Kanban View - Shows customer tickets in kanban board layout
        Access: Authenticated portal users (customers)
        """
        try:
            user = request.env.user
            if user.id == request.env.ref("base.public_user").id:
                return werkzeug.utils.redirect(
                    "/customer_support/login?error=Please login to access tickets"
                )

            if user.has_group("base.group_system"):
                return werkzeug.utils.redirect("/customer_support/admin_dashboard")

            tickets = (
                request.env["customer.support"]
                .search([("customer_id", "=", user.partner_id.id)])
                .sorted(key=lambda r: r.create_date, reverse=True)
            )

            ticket_counts = {
                "new": len(tickets.filtered(lambda t: t.state == "new")),
                "in_progress": len(tickets.filtered(lambda t: t.state == "in_progress")),
                "assigned": len(tickets.filtered(lambda t: t.state == "assigned")),
                "pending": len(tickets.filtered(lambda t: t.state == "pending")),
                "resolved": len(tickets.filtered(lambda t: t.state == "resolved")),
                "closed": len(tickets.filtered(lambda t: t.state == "closed")),
                "total": len(tickets),
            }

            response = request.render(
                "customer_support.customer_tickets_kanban",
                {
                    "user": user,
                    "tickets": tickets,
                    "ticket_counts": ticket_counts,
                    "page_name": "tickets_kanban",
                },
            )
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            return response

        except Exception as e:
            _logger.error(f"Kanban view error: {str(e)}")
            return werkzeug.utils.redirect("/customer_support/tickets")
