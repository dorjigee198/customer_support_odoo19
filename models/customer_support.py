from odoo import models, fields, api
from datetime import datetime


class CustomerSupport(models.Model):
    _name = "customer.support"
    _description = "Customer Support Ticket"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "create_date desc"

    name = fields.Char(
        string="Ticket Number", required=True, copy=False, readonly=True, default="New"
    )
    subject = fields.Char(string="Subject", required=True, tracking=True)
    description = fields.Text(string="Description", required=True)

    # ============ ADD THIS FIELD HERE ============
    # Project Information
    project_id = fields.Many2one(
        "customer_support.project",
        string="Project",
        required=False,
        tracking=True,
        help="The project this ticket belongs to",
    )
    # ============ END OF NEW FIELD ============

    # Customer Information
    customer_id = fields.Many2one(
        "res.partner",
        string="Customer",
        required=True,
        tracking=True,
        default=lambda self: self.env.user.partner_id,
    )
    customer_email = fields.Char(
        related="customer_id.email", string="Customer Email", store=True
    )
    customer_phone = fields.Char(
        related="customer_id.phone", string="Customer Phone", store=True
    )

    # Assignment
    assigned_to = fields.Many2one(
        "res.users", string="Assigned To (Focal Person)", tracking=True
    )
    assigned_by = fields.Many2one("res.users", string="Assigned By", tracking=True)
    assigned_date = fields.Datetime(string="Assigned Date", tracking=True)

    # Priority and Status
    priority = fields.Selection(
        [("low", "Low"), ("medium", "Medium"), ("high", "High"), ("urgent", "Urgent")],
        string="Priority",
        default="medium",
        required=True,
        tracking=True,
    )

    state = fields.Selection(
        [
            ("new", "New"),
            ("open", "Open"),
            ("in_progress", "In Progress"),
            ("resolved", "Resolved"),
            ("closed", "Closed"),
        ],
        string="Status",
        default="new",
        required=True,
        tracking=True,
    )

    # Timestamps
    resolved_date = fields.Datetime(string="Resolved Date", tracking=True)
    closed_date = fields.Datetime(string="Closed Date", tracking=True)

    # Notes
    internal_notes = fields.Text(string="Internal Notes")
    resolution_notes = fields.Text(string="Resolution Notes")

    # Computed Fields
    days_open = fields.Integer(
        string="Days Open", compute="_compute_days_open", store=True
    )
    is_overdue = fields.Boolean(string="Is Overdue", compute="_compute_is_overdue")

    @api.model_create_multi
    def create(self, vals_list):
        """
        Override create to handle both single dict and list of dicts
        and generate ticket numbers for new tickets
        """
        # Ensure vals_list is always a list
        if not isinstance(vals_list, list):
            vals_list = [vals_list]

        # Generate ticket numbers for new tickets
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = (
                    self.env["ir.sequence"].sudo().next_by_code("customer.support")
                    or "New"
                )

        tickets = super(CustomerSupport, self).create(vals_list)
        
        return tickets
    
    def _track_subtype(self, init_values):
        """
        Override to make tracking messages visible.
        This is a NEW method - doesn't change any existing behavior.
        """
        self.ensure_one()
        
        # Make state changes visible as comments
        if 'state' in init_values:
            return self.env.ref('mail.mt_comment')
        
        # Default behavior for other fields
        return super(CustomerSupport, self)._track_subtype(init_values)

    @api.depends("create_date", "closed_date")
    def _compute_days_open(self):
        """Calculate how many days the ticket has been open"""
        for record in self:
            if record.create_date:
                if record.closed_date:
                    delta = record.closed_date - record.create_date
                else:
                    delta = fields.Datetime.now() - record.create_date
                record.days_open = delta.days
            else:
                record.days_open = 0

    @api.depends("state", "days_open")
    def _compute_is_overdue(self):
        """Check if ticket is overdue (open for more than 7 days)"""
        for record in self:
            if record.state not in ["resolved", "closed"]:
                record.is_overdue = record.days_open > 7
            else:
                record.is_overdue = False

    def action_assign(self):
        """Assign ticket to a focal person"""
        self.ensure_one()
        if self.assigned_to:
            self.write(
                {
                    "state": "assigned",
                    "assigned_by": self.env.user.id,
                    "assigned_date": fields.Datetime.now(),
                }
            )
            # Send notification to assigned person
            self.message_post(
                body=f"Ticket assigned to {self.assigned_to.name}",
                subject="Ticket Assigned",
                partner_ids=[self.assigned_to.partner_id.id],
            )
        return True

    def action_start_progress(self):
        """Focal person starts working on ticket"""
        self.ensure_one()
        self.write({"state": "in_progress"})
        self.message_post(
            body=f"Ticket moved to In Progress by {self.env.user.name}",
            subject="Ticket In Progress",
        )
        return True

    def action_resolve(self):
        """Mark ticket as resolved"""
        self.ensure_one()
        self.write({"state": "resolved", "resolved_date": fields.Datetime.now()})
        # Notify customer
        if self.customer_id:
            self.message_post(
                body="Your ticket has been resolved. Please review the resolution.",
                subject="Ticket Resolved",
                partner_ids=[self.customer_id.id],
            )
        return True

    def action_close(self):
        """Close the ticket"""
        self.ensure_one()
        self.write({"state": "closed", "closed_date": fields.Datetime.now()})
        self.message_post(
            body=f"Ticket closed by {self.env.user.name}", subject="Ticket Closed"
        )
        return True

    def action_reopen(self):
        """Reopen a closed ticket"""
        self.ensure_one()
        self.write(
            {"state": "in_progress", "resolved_date": False, "closed_date": False}
        )
        self.message_post(
            body=f"Ticket reopened by {self.env.user.name}", subject="Ticket Reopened"
        )
        return True

    def action_pending(self):
        """Mark ticket as pending customer response"""
        self.ensure_one()
        self.write({"state": "pending"})
        if self.customer_id:
            self.message_post(
                body="We need more information from you to proceed with this ticket.",
                subject="Ticket Pending - Action Required",
                partner_ids=[self.customer_id.id],
            )
        return True

    @api.model
    def _cron_check_overdue_tickets(self):
        """Cron job to check and notify about overdue tickets"""
        overdue_tickets = self.search(
            [("state", "not in", ["resolved", "closed"]), ("days_open", ">", 7)]
        )

        for ticket in overdue_tickets:
            if ticket.assigned_to:
                ticket.message_post(
                    body=f"Reminder: This ticket has been open for {ticket.days_open} days.",
                    subject="Overdue Ticket Reminder",
                    partner_ids=[ticket.assigned_to.partner_id.id],
                )

        return True