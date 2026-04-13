# -*- coding: utf-8 -*-
"""
Authentication Controller
=========================
Handles all public-facing authentication routes for the Customer Support Portal:
  - Landing page
  - Login page (GET)
  - Login form submission and session handling (POST)
  - Logout (standard and manual)

No authentication is required for any route in this file.
Role-based redirection is handled after successful login.
"""

import logging
from odoo import http
from odoo.http import request
import werkzeug

_logger = logging.getLogger(__name__)


class CustomerSupportAuth(http.Controller):
    """
    Handles authentication flow:
      Public user → login → authenticate → redirect to correct dashboard
      Any user    → logout → landing page
    """

    # =========================================================================
    # LANDING PAGE
    # =========================================================================

    @http.route("/customer_support", type="http", auth="public", website=True)
    def landing_page(self, **kw):
        """
        Landing Page - Public welcome page.
        Authenticated users are redirected to their dashboard so the back
        button can never strand a logged-in user on the landing page.
        """
        user = request.env.user
        public_user = request.env.ref("base.public_user")
        if user and user.id != public_user.id and user.active:
            if user.has_group("base.group_system"):
                return werkzeug.utils.redirect("/customer_support/admin_dashboard")
            elif user.has_group("base.group_user"):
                return werkzeug.utils.redirect("/customer_support/support_dashboard")
            elif user.has_group("base.group_portal"):
                return werkzeug.utils.redirect("/customer_support/dashboard")

        response = request.render("customer_support.landing_page")
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        return response

    # =========================================================================
    # LOGIN
    # =========================================================================

    @http.route("/customer_support/login", type="http", auth="public", website=True)
    def support_login(self, **kw):
        """
        Login Page - Renders the custom login form
        Working: Shows login form with email/password fields
        Access: Public (no login required) — redirects already-authenticated users
        """
        user = request.env.user
        public_user = request.env.ref("base.public_user")
        if user and user.id != public_user.id and user.active:
            # User is already logged in — redirect to their dashboard
            if user.has_group("base.group_system"):
                return werkzeug.utils.redirect("/customer_support/admin_dashboard")
            elif user.has_group("base.group_user"):
                return werkzeug.utils.redirect("/customer_support/support_dashboard")
            elif user.has_group("base.group_portal"):
                return werkzeug.utils.redirect("/customer_support/dashboard")

        response = request.render(
            "customer_support.portal_login_page",
            {
                "error": kw.get("error", ""),
                "redirect": kw.get("redirect", ""),
            },
        )
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        return response

    @http.route(
        "/customer_support/authenticate",
        type="http",
        auth="public",
        methods=["POST"],
        website=True,
        csrf=False,
    )
    def support_authenticate(self, **post):
        """
        Authentication Handler - Processes login form submission
        Working: Validates credentials, creates session, redirects to the
                 correct dashboard based on the user's role.
                 If a redirect param is present (e.g. from an email link),
                 portal users are sent there instead of the default dashboard.
        Access: Public (no login required)

        Redirect targets:
          - System Admin  → /customer_support/admin_dashboard
          - Portal User   → redirect param OR /customer_support/dashboard
          - Internal User → /customer_support/support_dashboard
        """
        try:
            email = post.get("email", "").strip()
            password = post.get("password", "")

            # ← ADDED: read the redirect URL submitted as a hidden form field
            redirect_url = post.get("redirect", "").strip()

            _logger.info(f"Login attempt for email/login: {email}")

            # Validate that both fields are provided
            if not email or not password:
                return werkzeug.utils.redirect(
                    "/customer_support/login?error=Email and password are required"
                )

            # Ensure a database connection is available
            db = request.session.db
            if not db:
                return werkzeug.utils.redirect(
                    "/customer_support/login?error=Database connection error"
                )

            # Search for matching users by login OR email field
            uid = False
            users = (
                request.env["res.users"]
                .sudo()
                .search(["|", ("login", "=", email), ("email", "=", email)])
            )

            # Try authenticating each matching user until one succeeds
            for u in users:
                try:
                    auth_info = request.session.authenticate(
                        request.env,
                        {"type": "password", "login": u.login, "password": password},
                    )
                    uid = auth_info.get("uid") if auth_info else False
                except Exception as ex:
                    _logger.exception(f"authenticate raised for user {u.login}: {ex}")
                    uid = False
                if uid:
                    break

            if uid:
                user = request.env["res.users"].browse(uid)

                # Block inactive accounts immediately
                if not user.active:
                    request.session.logout()
                    return werkzeug.utils.redirect(
                        "/customer_support/login?error=Your account is inactive"
                    )

                # Route to the correct dashboard based on the user's role
                if user.has_group("base.group_system"):
                    # System administrator → admin dashboard (ignore redirect)
                    request.session["customer_support_login"] = True
                    return werkzeug.utils.redirect("/customer_support/admin_dashboard")

                elif user.has_group("base.group_portal"):
                    # Portal user (customer) → redirect param if present, else dashboard
                    request.session["customer_support_login"] = True
                    destination = (
                        redirect_url if redirect_url else "/customer_support/dashboard"
                    )  # ← FIXED
                    return werkzeug.utils.redirect(destination)

                elif user.has_group("base.group_user"):
                    # Internal user (focal person / support agent) → analytics dashboard
                    request.session["customer_support_login"] = True
                    return werkzeug.utils.redirect(
                        "/customer_support/support_dashboard"
                    )

                else:
                    # Authenticated but no recognised role — deny access
                    request.session.logout()
                    return werkzeug.utils.redirect(
                        "/customer_support/login?error=You do not have access to the customer support portal"
                    )

            # No user matched the supplied credentials
            return werkzeug.utils.redirect(
                "/customer_support/login?error=Invalid email or password"
            )

        except Exception as e:
            _logger.error(f"Login processing error: {str(e)}")
            return werkzeug.utils.redirect(
                "/customer_support/login?error=An error occurred during login. Please try again."
            )

    # =========================================================================
    # LOGOUT
    # =========================================================================

    @http.route("/customer_support/logout", type="http", auth="user", website=True)
    def support_logout(self, **kw):
        """
        Logout - Clears the session and redirects to the login page
        Access: All authenticated users
        """
        try:
            request.session.logout()
            return werkzeug.utils.redirect("/customer_support/login")
        except Exception as e:
            _logger.error(f"Logout error: {str(e)}")
            return werkzeug.utils.redirect("/customer_support/login")

    @http.route(
        "/customer_support/logout_manual", type="http", auth="user", website=True
    )
    def logout_manual(self):
        """
        Manual Logout - Alternative logout route
        Working: Clears the session and redirects to the login page
        Access: All authenticated users
        """
        request.session.logout()
        return request.redirect("/customer_support/login")
