# -*- coding: utf-8 -*-
"""
Admin User Management Controller
=================================
Handles all routes for system administrators related to:
  - Admin dashboard (tickets overview, analytics, user summary)
  - User management list (focal persons and customers)
  - Create user form and submission
  - Edit user form and update
  - Toggle user active/inactive
  - Delete (archive) user

Access: All routes require the user to be in base.group_system (admin).
Non-admin users are redirected to the customer dashboard.

Email notifications are delegated to EmailService:
  - Welcome email to new customers
  - Welcome email to new focal persons (different template)
"""

import logging
from odoo import http
from odoo.http import request
import werkzeug

from ..services.email_service import EmailService

_logger = logging.getLogger(__name__)


class CustomerSupportAdminUsers(http.Controller):
    """
    Handles the admin dashboard and all user management operations.
    Every route in this class is protected — non-admins are redirected away.
    """

    # =========================================================================
    # ADMIN DASHBOARD
    # =========================================================================

    @http.route(
        "/customer_support/admin_dashboard", type="http", auth="user", website=True
    )
    def admin_dashboard(self, **kw):
        """
        Admin Dashboard - Main overview for system administrators
        Working: Shows all tickets, analytics, performance stats, and a
                 user summary table across all roles.
        Access: Authenticated system administrators only
        """
        user = request.env.user

        # Block non-admin users from accessing this route
        if not user.has_group("base.group_system"):
            return werkzeug.utils.redirect("/customer_support/dashboard")

        # Fetch every ticket across all customers, newest first
        tickets = (
            request.env["customer.support"]
            .search([])
            .sorted(key=lambda r: r.create_date, reverse=True)
        )

        # Build a count summary per ticket status for the stat cards
        ticket_counts = {
            "new": len(tickets.filtered(lambda t: t.state == "new")),
            "assigned": len(tickets.filtered(lambda t: t.state == "assigned")),
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
            _logger.warning(f"Admin dashboard analytics failed: {str(e)}")
            # Safe defaults so the template never throws a KeyError
            open_tickets = ticket_counts.get("new", 0) + ticket_counts.get(
                "assigned", 0
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

        # Fetch all active non-system users for the User Management tab
        all_users = (
            request.env["res.users"]
            .search(
                [
                    ("id", "not in", [1, request.env.ref("base.public_user").id]),
                    ("active", "=", True),
                ]
            )
            .sorted(key=lambda r: r.create_date, reverse=True)
        )

        # Build user list with role labels and badge styles for the template
        users_data = []
        for u in all_users:
            if u.has_group("base.group_system"):
                role = "Admin"
                role_class = "primary"
            elif u.has_group("base.group_user"):
                role = "Focal Person"
                role_class = "info"
            elif u.has_group("base.group_portal"):
                role = "Customer"
                role_class = "secondary"
            else:
                role = "User"
                role_class = "secondary"

            users_data.append(
                {
                    "id": u.id,
                    "name": u.name,
                    "email": u.email or u.login,
                    "role": role,
                    "role_class": role_class,
                    "active": u.active,
                }
            )

        return request.render(
            "customer_support.admin_dashboard",
            {
                "user": user,
                "tickets": tickets,
                "ticket_counts": ticket_counts,
                "users_data": users_data,
                "analytics": analytics,
                "performance": performance,
                "page_name": "admin_dashboard",
            },
        )

    # =========================================================================
    # USER MANAGEMENT LIST
    # =========================================================================

    @http.route(
        "/customer_support/admin_dashboard/users",
        type="http",
        auth="user",
        website=True,
    )
    def admin_users_list(self, **kw):
        """
        User Management Page - Lists all users split by role
        Working: Displays focal persons and customers in separate sections
        Access: Authenticated system administrators only
        """
        user = request.env.user

        # Block non-admin users
        if not user.has_group("base.group_system"):
            return werkzeug.utils.redirect("/customer_support/dashboard")

        # Fetch all active non-system users
        all_users = (
            request.env["res.users"]
            .search(
                [
                    ("id", "not in", [1, request.env.ref("base.public_user").id]),
                    ("active", "=", True),
                ]
            )
            .sorted(key=lambda r: r.create_date, reverse=True)
        )

        # Split into focal persons and customers for separate display sections
        focal_persons = all_users.filtered(lambda u: u.has_group("base.group_user"))
        customers = all_users.filtered(
            lambda u: u.has_group("base.group_portal")
            and not u.has_group("base.group_user")
        )

        return request.render(
            "customer_support.admin_users_management",
            {
                "user": user,
                "focal_persons": focal_persons,
                "customers": customers,
                "page_name": "user_management",
                "success": kw.get("success", ""),
                "error": kw.get("error", ""),
            },
        )

    # =========================================================================
    # CREATE USER
    # =========================================================================

    @http.route(
        "/customer_support/admin_dashboard/create_user",
        type="http",
        auth="user",
        website=True,
    )
    def admin_create_user_form(self, **kw):
        """
        Create User Form - Displays the new user form
        Working: Renders form for creating focal persons or customers,
                 includes project selection dropdown
        Access: Authenticated system administrators only
        """
        user = request.env.user

        # Block non-admin users
        if not user.has_group("base.group_system"):
            return werkzeug.utils.redirect("/customer_support/dashboard")

        # Fetch all active projects to populate the dropdown
        projects = (
            request.env["customer_support.project"]
            .sudo()
            .search([("active", "=", True)])
        )

        return request.render(
            "customer_support.admin_create_user_form",
            {
                "user": user,
                "projects": projects,  # Passed to template for dropdown
                "page_name": "create_user",
                "error": kw.get("error", ""),
            },
        )

    @http.route(
        "/customer_support/admin_dashboard/submit_user",
        type="http",
        auth="user",
        methods=["POST"],
        website=True,
        csrf=True,
    )
    def admin_submit_user(self, **post):
        """
        Submit User - Handles new user creation
        Working: Creates partner record, then user record with the correct
                 access group. Sends a role-appropriate welcome email.
        Access: Authenticated system administrators only

        Email behaviour:
          - customer      → EmailService.send_welcome_email()
          - focal_person  → EmailService.send_welcome_email_focal_person()
          Email failures are non-fatal; user creation is already committed.
        """
        try:
            user = request.env.user

            # Block non-admin users
            if not user.has_group("base.group_system"):
                return werkzeug.utils.redirect("/customer_support/dashboard")

            # Normalize post data to a plain dict
            post_dict = dict(post) if not isinstance(post, dict) else post

            # ------------------------------------------------------------------
            # Extract and validate required fields
            # ------------------------------------------------------------------
            name = post_dict.get("name", "").strip()
            email = post_dict.get("email", "").strip()
            password = post_dict.get("password", "").strip()
            user_type = post_dict.get("user_type", "customer")
            phone = post_dict.get("phone", "").strip()
            project_id = post_dict.get("project_id")

            if not name:
                return werkzeug.utils.redirect(
                    "/customer_support/admin_dashboard/create_user?error=Name is required"
                )
            if not email:
                return werkzeug.utils.redirect(
                    "/customer_support/admin_dashboard/create_user?error=Email is required"
                )
            if not password:
                return werkzeug.utils.redirect(
                    "/customer_support/admin_dashboard/create_user?error=Password is required"
                )
            if not project_id:
                return werkzeug.utils.redirect(
                    "/customer_support/admin_dashboard/create_user?error=Project is required"
                )

            # Prevent duplicate accounts
            existing_user = (
                request.env["res.users"]
                .sudo()
                .search(["|", ("login", "=", email), ("email", "=", email)], limit=1)
            )
            if existing_user:
                return werkzeug.utils.redirect(
                    "/customer_support/admin_dashboard/create_user?error=Email already exists"
                )

            # ------------------------------------------------------------------
            # Create the partner record first (user record links to it)
            # ------------------------------------------------------------------
            partner = (
                request.env["res.partner"]
                .sudo()
                .create(
                    {
                        "name": name,
                        "email": email,
                        "phone": phone,
                        "is_company": False,
                        "project_id": int(project_id),  # Link partner to project
                    }
                )
            )

            # ------------------------------------------------------------------
            # Determine which Odoo group to assign based on user_type
            # ------------------------------------------------------------------
            if user_type == "focal_person":
                # Internal user — can access the backend and resolve tickets
                groups_to_add = [request.env.ref("base.group_user").id]
            else:
                # Portal user (customer) — restricted to the portal only
                groups_to_add = [request.env.ref("base.group_portal").id]

            # Create the user record (suppress Odoo's default reset-password email)
            new_user = (
                request.env["res.users"]
                .sudo()
                .with_context(no_reset_password=True)
                .create(
                    {
                        "name": name,
                        "login": email,
                        "email": email,
                        "partner_id": partner.id,
                        "password": password,
                        "active": True,
                    }
                )
            )

            # Assign the correct access group
            if groups_to_add:
                new_user.sudo().write({"group_ids": [(6, 0, groups_to_add)]})

            _logger.info(
                f"User created: {new_user.name} ({user_type}) "
                f"assigned to project {project_id} by {user.name}"
            )

            # ------------------------------------------------------------------
            # Send a role-appropriate welcome email.
            # Failures are caught and logged but do NOT roll back user creation.
            # ------------------------------------------------------------------
            try:
                if user_type == "customer":
                    # Welcome email with portal-specific messaging
                    EmailService.send_welcome_email(email, name, password)
                elif user_type == "focal_person":
                    # Welcome email with agent/support-specific messaging
                    EmailService.send_welcome_email_focal_person(email, name, password)
            except Exception as email_error:
                _logger.error(f"Welcome email failed for {email}: {str(email_error)}")

            user_type_label = (
                "Focal Person" if user_type == "focal_person" else "Customer"
            )
            return werkzeug.utils.redirect(
                f"/customer_support/admin_dashboard/users"
                f"?success={user_type_label} created successfully"
            )

        except Exception as e:
            _logger.exception(f"Create user error: {str(e)}")
            return werkzeug.utils.redirect(
                "/customer_support/admin_dashboard/create_user"
                "?error=Error creating user. Please try again."
            )

    # =========================================================================
    # EDIT USER
    # =========================================================================

    @http.route(
        "/customer_support/admin_dashboard/user/<int:user_id>/edit",
        type="http",
        auth="user",
        website=True,
    )
    def admin_edit_user_form(self, user_id, **kw):
        """
        Edit User Form - Displays the edit form pre-populated with user data
        Working: Loads existing user info and current role for the form
        Access: Authenticated system administrators only
        """
        current_user = request.env.user

        # Block non-admin users
        if not current_user.has_group("base.group_system"):
            return werkzeug.utils.redirect("/customer_support/dashboard")

        edit_user = request.env["res.users"].sudo().browse(user_id)
        if not edit_user.exists():
            return werkzeug.utils.redirect(
                "/customer_support/admin_dashboard/users?error=User not found"
            )

        # Determine the user's current role to pre-select in the form
        user_type = (
            "focal_person" if edit_user.has_group("base.group_user") else "customer"
        )

        return request.render(
            "customer_support.admin_edit_user_form",
            {
                "user": current_user,
                "edit_user": edit_user,
                "user_type": user_type,
                "page_name": "edit_user",
                "error": kw.get("error", ""),
            },
        )

    @http.route(
        "/customer_support/admin_dashboard/user/<int:user_id>/update",
        type="http",
        auth="user",
        methods=["POST"],
        website=True,
        csrf=True,
    )
    def admin_update_user(self, user_id, **post):
        """
        Update User - Processes the edit user form submission
        Working: Updates partner and user records; swaps access group if
                 the user_type has changed; optionally resets password.
        Access: Authenticated system administrators only
        """
        try:
            current_user = request.env.user

            # Block non-admin users
            if not current_user.has_group("base.group_system"):
                return werkzeug.utils.redirect("/customer_support/dashboard")

            edit_user = request.env["res.users"].sudo().browse(user_id)
            if not edit_user.exists():
                return werkzeug.utils.redirect(
                    "/customer_support/admin_dashboard/users?error=User not found"
                )

            # Normalize post data to a plain dict
            post_dict = dict(post) if not isinstance(post, dict) else post

            # ------------------------------------------------------------------
            # Extract and validate required fields
            # ------------------------------------------------------------------
            name = post_dict.get("name", "").strip()
            email = post_dict.get("email", "").strip()
            phone = post_dict.get("phone", "").strip()
            user_type = post_dict.get("user_type", "customer")
            password = post_dict.get("password", "").strip()

            if not name:
                return werkzeug.utils.redirect(
                    f"/customer_support/admin_dashboard/user/{user_id}/edit"
                    "?error=Name is required"
                )
            if not email:
                return werkzeug.utils.redirect(
                    f"/customer_support/admin_dashboard/user/{user_id}/edit"
                    "?error=Email is required"
                )

            # Prevent duplicate email — exclude the user currently being edited
            existing_user = (
                request.env["res.users"]
                .sudo()
                .search(
                    [
                        "|",
                        ("login", "=", email),
                        ("email", "=", email),
                        ("id", "!=", user_id),
                    ],
                    limit=1,
                )
            )
            if existing_user:
                return werkzeug.utils.redirect(
                    f"/customer_support/admin_dashboard/user/{user_id}/edit"
                    "?error=Email already exists"
                )

            # Update the linked partner record
            edit_user.partner_id.sudo().write(
                {"name": name, "email": email, "phone": phone}
            )

            # Build user update payload
            update_vals = {
                "name": name,
                "login": email,
                "email": email,
            }

            # Only update password if a new one was provided
            if password:
                update_vals["password"] = password

            # Swap access group to match the selected user_type
            if user_type == "focal_person":
                groups_to_add = [request.env.ref("base.group_user").id]
                groups_to_remove = [request.env.ref("base.group_portal").id]
            else:
                groups_to_add = [request.env.ref("base.group_portal").id]
                groups_to_remove = [request.env.ref("base.group_user").id]

            update_vals["group_ids"] = [
                (4, groups_to_add[0]),  # (4, id) → link/add group
                (3, groups_to_remove[0]),  # (3, id) → unlink/remove group
            ]

            edit_user.sudo().write(update_vals)

            _logger.info(f"User updated: {edit_user.name} by {current_user.name}")

            return werkzeug.utils.redirect(
                "/customer_support/admin_dashboard/users?success=User updated successfully"
            )

        except Exception as e:
            _logger.exception(f"Update user error: {str(e)}")
            return werkzeug.utils.redirect(
                f"/customer_support/admin_dashboard/user/{user_id}/edit"
                "?error=Error updating user"
            )

    # =========================================================================
    # TOGGLE USER ACTIVE / INACTIVE
    # =========================================================================

    @http.route(
        "/customer_support/admin_dashboard/user/<int:user_id>/toggle_active",
        type="http",
        auth="user",
        methods=["POST"],
        website=True,
        csrf=True,
    )
    def admin_toggle_user_active(self, user_id, **post):
        """
        Toggle User Active/Inactive - Flips a user's active flag
        Working: Activates an inactive user or deactivates an active one.
                 Admins cannot deactivate their own account.
        Access: Authenticated system administrators only
        """
        try:
            current_user = request.env.user

            # Block non-admin users
            if not current_user.has_group("base.group_system"):
                return werkzeug.utils.redirect("/customer_support/dashboard")

            edit_user = request.env["res.users"].sudo().browse(user_id)
            if not edit_user.exists():
                return werkzeug.utils.redirect(
                    "/customer_support/admin_dashboard/users?error=User not found"
                )

            # Prevent admins from locking themselves out
            if edit_user.id == current_user.id:
                return werkzeug.utils.redirect(
                    "/customer_support/admin_dashboard/users"
                    "?error=Cannot deactivate yourself"
                )

            # Flip the active flag
            new_status = not edit_user.active
            edit_user.sudo().write({"active": new_status})

            status_text = "activated" if new_status else "deactivated"
            _logger.info(f"User {status_text}: {edit_user.name} by {current_user.name}")

            return werkzeug.utils.redirect(
                f"/customer_support/admin_dashboard/users"
                f"?success=User {status_text} successfully"
            )

        except Exception as e:
            _logger.exception(f"Toggle user active error: {str(e)}")
            return werkzeug.utils.redirect(
                "/customer_support/admin_dashboard/users"
                "?error=Error updating user status"
            )

    # =========================================================================
    # DELETE (ARCHIVE) USER
    # =========================================================================

    @http.route(
        "/customer_support/admin_dashboard/user/<int:user_id>/delete",
        type="http",
        auth="user",
        methods=["POST"],
        website=True,
        csrf=True,
    )
    def admin_delete_user(self, user_id, **post):
        """
        Delete User - Soft-deletes a user by archiving them
        Working: Sets active=False instead of removing the record, preserving
                 all historical data (tickets, messages, etc.).
                 Admins cannot delete their own account.
        Access: Authenticated system administrators only
        """
        try:
            current_user = request.env.user

            # Block non-admin users
            if not current_user.has_group("base.group_system"):
                return werkzeug.utils.redirect("/customer_support/dashboard")

            edit_user = request.env["res.users"].sudo().browse(user_id)
            if not edit_user.exists():
                return werkzeug.utils.redirect(
                    "/customer_support/admin_dashboard/users?error=User not found"
                )

            # Prevent admins from deleting themselves
            if edit_user.id == current_user.id:
                return werkzeug.utils.redirect(
                    "/customer_support/admin_dashboard/users"
                    "?error=Cannot delete yourself"
                )

            user_name = edit_user.name

            # Soft-delete: archive instead of unlink to preserve history
            edit_user.sudo().write({"active": False})

            _logger.info(f"User archived: {user_name} by {current_user.name}")

            return werkzeug.utils.redirect(
                "/customer_support/admin_dashboard/users"
                "?success=User deleted successfully"
            )

        except Exception as e:
            _logger.exception(f"Delete user error: {str(e)}")
            return werkzeug.utils.redirect(
                "/customer_support/admin_dashboard/users?error=Error deleting user"
            )
