# -*- coding: utf-8 -*-
"""
Customer Support Ticket Log
============================
A lightweight, unified activity log for the ticket detail timeline.
Captures: status changes, assignment changes, SLA events, ticket creation.

Written to automatically by:
  - CustomerSupport.create()     → 'created' event
  - CustomerSupport.write()      → 'status' and 'assign' events
  - _cron_check_sla_breaches()   → 'sla' events
"""

from odoo import models, fields


class CustomerSupportTicketLog(models.Model):
    _name = "customer.support.ticket.log"
    _description = "Ticket Activity Log"
    _order = "timestamp desc"

    ticket_id = fields.Many2one(
        "customer.support",
        string="Ticket",
        required=True,
        ondelete="cascade",
        index=True,
    )

    event_type = fields.Selection(
        [
            ("created", "Ticket Created"),
            ("status", "Status Changed"),
            ("assign", "Assignment Changed"),
            ("sla", "SLA Event"),
        ],
        string="Event Type",
        required=True,
        index=True,
    )

    # Who triggered it
    actor_id = fields.Many2one(
        "res.users",
        string="Triggered By",
        default=lambda self: self.env.user,
    )

    # Human-readable summary shown in the timeline title
    summary = fields.Char(string="Summary", required=True)

    # Optional detail text shown in the timeline body
    detail = fields.Text(string="Detail")

    # For status changes: store old and new values
    old_value = fields.Char(string="Previous Value")
    new_value = fields.Char(string="New Value")

    timestamp = fields.Datetime(
        string="Timestamp",
        required=True,
        default=fields.Datetime.now,
        index=True,
    )
