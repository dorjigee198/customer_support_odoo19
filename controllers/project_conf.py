# controllers/customer_support_project_controller.py
from odoo import http
from odoo.http import request
import logging

_logger = logging.getLogger(__name__)


class CustomerSupportProjectController(http.Controller):
    @http.route(
        "/customer_support/admin_dashboard/system_configuration",
        type="http",
        auth="user",
        website=True,
    )
    def system_configuration_page(self, **kwargs):
        """Display the system configuration page"""
        return request.render(
            "customer_support.system_configuration_template",
            {"page_name": "system_configuration"},
        )

    @http.route(
        "/customer_support/admin_dashboard/projects/create",
        type="http",
        auth="user",
        methods=["POST"],
        website=True,
        csrf=True,
    )
    def customer_support_create_project(self, **post):
        """Handle project + project configuration form submission"""
        try:
            # Models
            ProjectModel = request.env["customer_support.project"].sudo()
            ConfigModel = request.env["customer_support.project.config"].sudo()

            # Step 1: Create main project
            project = ProjectModel.create(
                {
                    "name": post.get("project_name"),
                    "code": post.get("project_key"),
                }
            )

            # Step 2: Prepare compliance booleans
            compliance_fields = ["gdpr", "hipaa", "pci_dss", "iso27001"]
            compliance_kwargs = {
                f"compliance_{c}": bool(post.get(f"compliance_{c}"))
                for c in compliance_fields
            }

            # Step 3: Create project configuration
            ConfigModel.create(
                {
                    "project_id": project.id,
                    "project_type": post.get("project_type"),
                    "start_date": post.get("start_date"),
                    "end_date": post.get("end_date"),
                    "programming_languages": post.get("programming_languages"),
                    "frameworks": post.get("frameworks"),
                    "databases": post.get("databases"),
                    "project_goals": post.get("project_goals"),
                    **compliance_kwargs,
                }
            )

            _logger.info(f"Project + Config created: {project.name} (ID: {project.id})")

            return request.redirect(
                f"/customer_support/admin_dashboard/system_configuration?project_created=1&project_id={project.id}&tab=project"
            )

        except Exception as e:
            _logger.error(f"Error creating project configuration: {str(e)}")
            return request.redirect(
                f"/customer_support/admin_dashboard/system_configuration?error=1&error_msg={str(e)}&tab=project"
            )

    @http.route(
        "/customer_support/admin_dashboard/projects/update/<int:project_id>",
        type="http",
        auth="user",
        methods=["POST"],
        website=True,
        csrf=True,
    )
    def customer_support_update_project(self, project_id, **post):
        """Handle project + config update"""
        try:
            ProjectModel = request.env["customer_support.project"].sudo()
            ConfigModel = request.env["customer_support.project.config"].sudo()

            project = ProjectModel.browse(project_id)
            config = ConfigModel.search([("project_id", "=", project.id)], limit=1)

            if not project.exists():
                return request.redirect(
                    "/customer_support/admin_dashboard/system_configuration?error=1&error_msg=Project not found&tab=project"
                )

            # Update main project
            project.write(
                {
                    "name": post.get("project_name"),
                    "code": post.get("project_key"),
                }
            )

            # Update or create config
            compliance_fields = ["gdpr", "hipaa", "pci_dss", "iso27001"]
            compliance_kwargs = {
                f"compliance_{c}": bool(post.get(f"compliance_{c}"))
                for c in compliance_fields
            }

            config_vals = {
                "project_type": post.get("project_type"),
                "start_date": post.get("start_date"),
                "end_date": post.get("end_date"),
                "programming_languages": post.get("programming_languages"),
                "frameworks": post.get("frameworks"),
                "databases": post.get("databases"),
                "project_goals": post.get("project_goals"),
                **compliance_kwargs,
            }

            if config.exists():
                config.write(config_vals)
            else:
                ConfigModel.create({**config_vals, "project_id": project.id})

            _logger.info(f"Project + Config updated: {project.name} (ID: {project.id})")

            return request.redirect(
                f"/customer_support/admin_dashboard/system_configuration?project_updated=1&project_id={project.id}&tab=project"
            )

        except Exception as e:
            _logger.error(f"Error updating project configuration: {str(e)}")
            return request.redirect(
                f"/customer_support/admin_dashboard/system_configuration?error=1&error_msg={str(e)}&tab=project"
            )

    @http.route(
        "/customer_support/admin_dashboard/projects/delete/<int:project_id>",
        type="http",
        auth="user",
        methods=["POST"],
        website=True,
        csrf=True,
    )
    def customer_support_delete_project(self, project_id, **post):
        """Handle project deletion"""
        try:
            ProjectModel = request.env["customer_support.project"].sudo()
            ConfigModel = request.env["customer_support.project.config"].sudo()

            project = ProjectModel.browse(project_id)
            config = ConfigModel.search([("project_id", "=", project.id)])

            if not project.exists():
                return request.redirect(
                    "/customer_support/admin_dashboard/system_configuration?error=1&error_msg=Project not found&tab=project"
                )

            project_name = project.name
            # Delete config first to maintain integrity
            config.unlink()
            project.unlink()

            _logger.info(f"Project + Config deleted: {project_name}")

            return request.redirect(
                "/customer_support/admin_dashboard/system_configuration?project_deleted=1&tab=project"
            )

        except Exception as e:
            _logger.error(f"Error deleting project configuration: {str(e)}")
            return request.redirect(
                f"/customer_support/admin_dashboard/system_configuration?error=1&error_msg={str(e)}&tab=project"
            )

    @http.route(
        "/customer_support/admin_dashboard/projects/get/<int:project_id>",
        type="json",
        auth="user",
        methods=["POST"],
        csrf=True,
    )
    def customer_support_get_project(self, project_id):
        """Get project + config details (AJAX)"""
        try:
            ProjectModel = request.env["customer_support.project"].sudo()
            ConfigModel = request.env["customer_support.project.config"].sudo()

            project = ProjectModel.browse(project_id)
            config = ConfigModel.search([("project_id", "=", project.id)], limit=1)

            if not project.exists():
                return {"error": "Project not found"}

            # Parse compliance
            compliance = []
            if config.exists():
                for c in ["gdpr", "hipaa", "pci_dss", "iso27001"]:
                    if getattr(config, f"compliance_{c}"):
                        compliance.append(c.upper())

            return {
                "success": True,
                "project": {
                    "id": project.id,
                    "name": project.name,
                    "project_key": project.code,
                    "project_type": config.project_type if config.exists() else "",
                    "goals_objectives": config.project_goals if config.exists() else "",
                    "start_date": (
                        config.start_date.strftime("%Y-%m-%d")
                        if config.exists() and config.start_date
                        else ""
                    ),
                    "end_date": (
                        config.end_date.strftime("%Y-%m-%d")
                        if config.exists() and config.end_date
                        else ""
                    ),
                    "programming_languages": (
                        config.programming_languages if config.exists() else ""
                    ),
                    "frameworks": config.frameworks if config.exists() else "",
                    "databases": config.databases if config.exists() else "",
                    "compliance_standards": compliance,
                },
            }

        except Exception as e:
            _logger.error(f"Error fetching project configuration: {str(e)}")
            return {"error": str(e)}
