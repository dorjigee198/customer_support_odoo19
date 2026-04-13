# controllers/customer_support_project_controller.py
from odoo import http
from odoo.http import request
import logging
from ..services.email_service import EmailService

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
        projects = request.env["customer_support.project"].sudo().search(
            [], order="name asc"
        )
        return request.render(
            "customer_support.system_configuration_template",
            {
                "page_name": "system_configuration",
                "projects": projects,
            },
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
            project_name = (post.get("project_name") or "").strip()
            project_type = (post.get("project_type") or "").strip()
            start_date = (post.get("start_date") or "").strip()

            if not project_name:
                return request.redirect(
                    "/customer_support/admin_dashboard/system_configuration?error=1&error_msg=Project+name+is+required&tab=project"
                )
            if not project_type:
                return request.redirect(
                    "/customer_support/admin_dashboard/system_configuration?error=1&error_msg=Project+type+is+required&tab=project"
                )
            if not start_date:
                return request.redirect(
                    "/customer_support/admin_dashboard/system_configuration?error=1&error_msg=Start+date+is+required&tab=project"
                )

            # Models
            ProjectModel = request.env["customer_support.project"].sudo()
            ConfigModel = request.env["customer_support.project.config"].sudo()

            # Step 1: Create main project
            project = ProjectModel.create(
                {
                    "name": project_name,
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
                    "project_type": project_type,
                    "start_date": start_date,
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

    # =========================================================================
    # PROJECT MEMBERS — helper
    # =========================================================================

    def _member_dict(self, m):
        name = m.user_id.name if m.user_id else (m.member_name or "")
        email = m.user_id.email if m.user_id else (m.member_email or "")
        initials = "".join(p[0].upper() for p in name.split()[:2]) if name else "?"
        return {
            "id": m.id,
            "user_id": m.user_id.id if m.user_id else False,
            "name": name,
            "email": email,
            "role": m.role,
            "role_label": m.role_label,
            "initials": initials,
        }

    # =========================================================================
    # FOCAL PERSON — load list & assign to project
    # =========================================================================

    @http.route(
        "/customer_support/admin_dashboard/focal_persons",
        type="json",
        auth="user",
        methods=["POST"],
        csrf=True,
    )
    def get_focal_persons(self, **kw):
        """Return all active internal (focal person) users for the dropdown."""
        try:
            internal_group_id = request.env.ref("base.group_user").id
            system_group_id = request.env.ref("base.group_system").id
            users = (
                request.env["res.users"]
                .sudo()
                .search([
                    ("active", "=", True),
                    ("share", "=", False),
                    ("group_ids", "in", [internal_group_id]),
                    ("group_ids", "not in", [system_group_id]),
                ])
            )
            return {
                "success": True,
                "users": [
                    {
                        "id": u.id,
                        "name": u.name,
                        "email": u.email or "",
                        "initials": "".join(p[0].upper() for p in u.name.split()[:2]),
                    }
                    for u in users
                ],
            }
        except Exception as e:
            _logger.error(f"get_focal_persons error: {e}")
            return {"error": str(e)}

    @http.route(
        "/customer_support/admin_dashboard/projects/<int:project_id>/focal/assign",
        type="json",
        auth="user",
        methods=["POST"],
        csrf=True,
    )
    def assign_focal_person(self, project_id, **kw):
        """Assign (or replace) the focal person for a project."""
        try:
            user_id = kw.get("user_id")
            if not user_id:
                return {"error": "user_id is required"}

            project = request.env["customer_support.project"].sudo().browse(project_id)
            if not project.exists():
                return {"error": "Project not found"}

            # Remove any existing focal person records for this project
            existing_focal = (
                request.env["customer_support.project.member"]
                .sudo()
                .search([("project_id", "=", project_id), ("role", "=", "focal_person")])
            )
            existing_focal.unlink()

            # Create the new focal person record
            member = request.env["customer_support.project.member"].sudo().create({
                "project_id": project_id,
                "user_id": user_id,
                "role": "focal_person",
            })

            return {"success": True, "member": self._member_dict(member)}
        except Exception as e:
            _logger.error(f"assign_focal_person error: {e}")
            return {"error": str(e)}

    @http.route(
        "/customer_support/admin_dashboard/projects/<int:project_id>/focal/remove",
        type="json",
        auth="user",
        methods=["POST"],
        csrf=True,
    )
    def remove_focal_person(self, project_id, **kw):
        """Remove the focal person assignment from a project."""
        try:
            existing_focal = (
                request.env["customer_support.project.member"]
                .sudo()
                .search([("project_id", "=", project_id), ("role", "=", "focal_person")])
            )
            existing_focal.unlink()
            return {"success": True}
        except Exception as e:
            _logger.error(f"remove_focal_person error: {e}")
            return {"error": str(e)}

    # =========================================================================
    # TEAM MEMBERS (non-focal, name+email entries)
    # =========================================================================

    @http.route(
        "/customer_support/admin_dashboard/projects/<int:project_id>/members",
        type="json",
        auth="user",
        methods=["POST"],
        csrf=True,
    )
    def get_project_members(self, project_id, **kw):
        """Return focal person + team members for a project."""
        try:
            members = (
                request.env["customer_support.project.member"]
                .sudo()
                .search([("project_id", "=", project_id)])
            )
            focal = [m for m in members if m.role == "focal_person"]
            team = [m for m in members if m.role != "focal_person"]
            return {
                "success": True,
                "focal": self._member_dict(focal[0]) if focal else None,
                "members": [self._member_dict(m) for m in team],
            }
        except Exception as e:
            _logger.error(f"get_project_members error: {e}")
            return {"error": str(e)}

    @http.route(
        "/customer_support/admin_dashboard/projects/<int:project_id>/members/add",
        type="json",
        auth="user",
        methods=["POST"],
        csrf=True,
    )
    def add_project_member(self, project_id, **kw):
        """Add a team member (non-focal) by name + email + role."""
        try:
            name = (kw.get("name") or "").strip()
            email = (kw.get("email") or "").strip()
            role = kw.get("role") or "other"

            if not name:
                return {"error": "Name is required"}
            if role == "focal_person":
                return {"error": "Use the focal person section to assign a focal person"}

            project = request.env["customer_support.project"].sudo().browse(project_id)
            if not project.exists():
                return {"error": "Project not found"}

            member = request.env["customer_support.project.member"].sudo().create({
                "project_id": project_id,
                "member_name": name,
                "member_email": email,
                "role": role,
            })

            # Send board invite emails for every active ticket in this project
            if email:
                try:
                    base_url = request.env["ir.config_parameter"].sudo().get_param("web.base.url", "").rstrip("/")
                    tickets = request.env["customer.support"].sudo().search([
                        ("project_id", "=", project_id),
                        ("state", "not in", ["closed"]),
                    ])
                    for ticket in tickets:
                        if not ticket.board_token:
                            import secrets
                            ticket.sudo().write({"board_token": secrets.token_urlsafe(32)})
                        board_url = f"{base_url}/board/{ticket.board_token}"
                        EmailService.send_board_invite(name, email, ticket, board_url)
                except Exception as mail_err:
                    _logger.warning(f"Board invite email failed: {mail_err}")

            return {"success": True, "member": self._member_dict(member)}
        except Exception as e:
            _logger.error(f"add_project_member error: {e}")
            return {"error": str(e)}

    @http.route(
        "/customer_support/admin_dashboard/projects/members/<int:member_id>/remove",
        type="json",
        auth="user",
        methods=["POST"],
        csrf=True,
    )
    def remove_project_member(self, member_id, **kw):
        """Remove a team member from a project."""
        try:
            member = (
                request.env["customer_support.project.member"]
                .sudo()
                .browse(member_id)
            )
            if not member.exists():
                return {"error": "Member record not found"}
            member.unlink()
            return {"success": True}
        except Exception as e:
            _logger.error(f"remove_project_member error: {e}")
            return {"error": str(e)}

    @http.route(
        "/customer_support/admin_dashboard/projects/<int:project_id>/documents",
        type="json",
        auth="user",
        methods=["POST"],
        csrf=True,
    )
    def get_project_documents(self, project_id, **kw):
        """Return documents linked to a project."""
        try:
            if not request.env.user.has_group("base.group_system"):
                return {"error": "Access denied"}
            docs = (
                request.env["dc.knowledge.document"]
                .sudo()
                .search([("project_id", "=", project_id), ("active", "=", True)],
                        order="create_date desc")
            )
            return {
                "success": True,
                "documents": [
                    {
                        "id": d.id,
                        "name": d.name,
                        "filename": d.filename or "",
                        "file_type": d.file_type or "other",
                        "category": d.category or "other",
                        "state": d.state or "pending",
                        "created": d.create_date.strftime("%b %d, %Y") if d.create_date else "",
                    }
                    for d in docs
                ],
            }
        except Exception as e:
            _logger.error(f"get_project_documents error: {e}")
            return {"error": str(e)}

    @http.route(
        "/customer_support/admin_dashboard/documents/<int:doc_id>/delete",
        type="json",
        auth="user",
        methods=["POST"],
        csrf=True,
    )
    def delete_project_document(self, doc_id, **kw):
        """Delete a knowledge document."""
        try:
            if not request.env.user.has_group("base.group_system"):
                return {"error": "Access denied"}
            doc = request.env["dc.knowledge.document"].sudo().browse(doc_id)
            if not doc.exists():
                return {"error": "Document not found"}
            doc.unlink()
            return {"success": True}
        except Exception as e:
            _logger.error(f"delete_project_document error: {e}")
            return {"error": str(e)}
