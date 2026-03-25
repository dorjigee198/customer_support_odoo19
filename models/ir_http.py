# -*- coding: utf-8 -*-
"""
IR HTTP Override
================
Intercepts Odoo's default /web/login redirect and replaces it with
the custom portal login page for all /customer_support/* routes.
"""

import logging
from odoo import models
from odoo.http import request

_logger = logging.getLogger(__name__)


class IrHttp(models.AbstractModel):
    _inherit = "ir.http"

    @classmethod
    def _get_login_redirect_url(cls, uid, redirect=None):
        """
        Override Odoo's default login redirect.
        For any /customer_support/* route, redirect to our custom login
        page with a `next` param instead of /web/login.
        """
        if request and request.httprequest:
            path = request.httprequest.path
            if path.startswith("/customer_support/"):
                next_url = path
                # Preserve query string if any
                qs = request.httprequest.query_string.decode("utf-8")
                if qs:
                    next_url = f"{path}?{qs}"
                _logger.info(f"Intercepting login redirect for path: {path}")
                return f"/customer_support/login?next={next_url}"

        # Fall back to Odoo's default behaviour for everything else
        return super()._get_login_redirect_url(uid, redirect=redirect)
