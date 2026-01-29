{
    "name": "Customer Support",
    "version": "19.0.1.0.0",
    "category": "Services",
    "summary": "Customer Support Management System",
    "description": """
        Custom Customer Support Module
        ================================
        Manage customer support tickets and requests.
    """,
    "author": "Dragon Coders",
    "website": "https://www.yourwebsite.com",
    "depends": ["base", "mail", "web", "portal"],
    "external_dependencies": {
        "python": ["openai"],
    },
    "data": [
        "security/ir.model.access.csv",
        "data/sequence.xml",
        "views/customer_support_views.xml",
        "views/templates/landing_page.xml",
        "views/templates/portal_login.xml",
        "views/portal_dashboard.xml",
        "views/portal_tickets.xml",
        "views/support_dashboard.xml",
        "views/create_ticket.xml",
        "views/edit_profile.xml",
        "views/chatbot_page.xml",
        "views/admin_dashboard.xml",
        "views/user_management.xml",
        "views/templates/ticket_detail.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "customer_support/static/src/css/customer_support.css",
            "customer_support/static/src/js/customer_support.js",
        ],
        "web.assets_frontend": [
            "customer_support/static/src/css/portal_login.css",
            "customer_support/static/src/js/portal_login.js",
            "customer_support/static/src/css/portal_dashboard.css",
            "customer_support/static/src/css/support_dashboard.css",
            "customer_support/static/src/js/chatbot.js",
        ],
    },
    "installable": True,
    "application": True,
    "auto_install": False,
    "license": "LGPL-3",
}
