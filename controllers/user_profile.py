# -*- coding: utf-8 -*-
"""
Profile Controller
==================
Handles user profile management:
- Display profile page
- Update profile info and password
"""

import logging
from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class UserProfile(http.Controller):

    @http.route(
        "/customer_support/profile",
        type="http",
        auth="user",
        website=True,
    )
    def display_profile(self, **kwargs):
        """
        Display Profile - Shows user profile information
        Working: Displays user details and password change form
        Access: All authenticated users
        """
        return request.render(
            "customer_support.portal_profile_page",
            {
                "user": request.env.user,
                "error": kwargs.get("error"),
                "success": kwargs.get("success"),
            },
        )

    @http.route(
        "/customer_support/profile/update",
        type="http",
        auth="user",
        methods=["POST"],
        website=True,
    )
    def update_profile(self, **post):
        """
        Update Profile - Handles profile updates and password changes
        Working: Updates user information and validates password changes
        Access: All authenticated users
        """
        user = request.env.user

        # Update basic profile info (sudo needed for portal users with restricted access)
        user.sudo().write({"name": post.get("name")})
        user.partner_id.sudo().write({"phone": post.get("phone")})

        # Handle optional password change
        old_pwd = post.get("old_pwd")
        new_pwd = post.get("new_pwd")
        confirm_pwd = post.get("confirm_pwd")

        if old_pwd and new_pwd:
            # Verify the two new-password fields match before proceeding
            if new_pwd != confirm_pwd:
                return request.render(
                    "customer_support.portal_profile_page",
                    {"user": user, "error": "New passwords do not match."},
                )

            try:
                # Odoo's built-in method handles hashing and old-password verification
                user.change_password(old_pwd, new_pwd)
            except Exception:
                return request.render(
                    "customer_support.portal_profile_page",
                    {"user": user, "error": "Incorrect current password."},
                )

        return request.redirect("/customer_support/profile?success=1")
