from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError


class ProductGroupCategory(models.Model):
    _name = "product.group.category"
    _description = "Group Category of Product"
    _order = "name"

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)


class ProductTemplate(models.Model):
    _inherit = "product.template"

class PurchaseRequest(models.Model):
    _name = "purchase.request"
    _description = "Purchase Request"
    _inherit = ["mail.thread", "mail.activity.mixin", "approval.matrix.mixin"]
    _order = "date_order desc, id desc"
    _check_company_auto = True

    name = fields.Char(
        string="Reference",
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _("New"),
        tracking=True,
    )
    date_order = fields.Datetime(string="Date", default=fields.Datetime.now, required=True)
    user_id = fields.Many2one(
        "res.users",
        string="Request By",
        required=True,
        default=lambda self: self.env.user,
        tracking=True,
    )
    employee_id = fields.Many2one(
        "hr.employee",
        string="Request By Employee",
        required=True,
        default=lambda self: self._default_employee(),
        check_company=True,
    )
    department_id = fields.Many2one(
        "hr.department",
        string="Department",
        related="employee_id.department_id",
        store=True,
        readonly=True,
    )
    is_asset = fields.Boolean(string="Asset")
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("waiting_approval", "Waiting Approval"),
            ("approved", "Approved"),
            ("reject", "Reject"),
        ],
        default="draft",
        required=True,
        copy=False,
        tracking=True,
        index=True,
    )
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company, index=True
    )
    is_over_process = fields.Boolean(string="Over Process", readonly=True)
    date_request = fields.Datetime(string="Requestion Date", readonly=True)
    date_confirmed = fields.Datetime(string="Confirmed Date", readonly=True)
    confirmed_by = fields.Many2one("res.users", string="Confirmed By", readonly=True)
    manager_department = fields.Many2one(
        "res.users", string="Department Manager", readonly=True
    )
    date_approval_department = fields.Datetime(
        string="Department Approval Date", readonly=True
    )
    approved_by = fields.Many2one("res.users", string="Approved By", readonly=True)
    date_approved = fields.Datetime(string="Approved Date", readonly=True)
    rejected_by = fields.Many2one("res.users", string="Rejected By", readonly=True)
    date_rejected = fields.Datetime(string="Rejected Date", readonly=True)
    reject_message = fields.Text(string="Reject Reason", readonly=True)

    line_ids = fields.One2many(
        "purchase.request.line",
        "purchase_request_id",
        string="Purchase Request Line",
        copy=True,
    )

    total_qty = fields.Float(
        string="Total Quantity",
        compute="_compute_total_qty",
        store=True,
        tracking=True,
    )

    is_locked = fields.Boolean(
        compute="_compute_is_locked"
    )

    @api.model
    def _default_employee(self, user=None, company=None):
        user = user or self.env.user
        company = company or self.env.company
        return self.env["hr.employee"].sudo().search(
            [("user_id", "=", user.id), ("company_id", "=", company.id)], limit=1
        )

    @api.model_create_multi
    def create(self, vals_list):
        for values in vals_list:
            company = self.env["res.company"].browse(
                values.get("company_id") or self.env.company.id
            )
            if values.get("name", _("New")) == _("New"):
                values["name"] = (
                    self.env["ir.sequence"]
                    .with_company(company)
                    .next_by_code("purchase.request")
                    or _("New")
                )
            if not values.get("employee_id"):
                employee = self._default_employee(
                    self.env["res.users"].browse(values.get("user_id") or self.env.user.id),
                    company,
                )
                if employee:
                    values["employee_id"] = employee.id
            if not self.env.context.get("purchase_request_migration"):
                values["state"] = "draft"
        return super().create(vals_list)

    @api.onchange("user_id", "company_id")
    def _onchange_user(self):
        employee = self._default_employee(self.user_id, self.company_id)
        if employee:
            self.employee_id = employee

    @api.depends("line_ids.qty")
    def _compute_total_qty(self):
        for request in self:
            request.total_qty = sum(
                request.line_ids.mapped("qty")
            )


    @api.depends("state")
    def _compute_is_locked(self):
        for request in self:
            request.is_locked = request.state not in (
                "draft",
                "reject",
            )

    @api.constrains("line_ids.qty")
    def _check_line_quantity(self):
        for request in self:
            if request.line_ids.filtered(lambda line: line.qty <= 0):
                raise ValidationError(_("Purchase request quantities must be positive."))

    def write(self, values):
        protected = {
            "date_order",
            "user_id",
            "employee_id",
            "company_id",
            "is_asset",
            "line_ids",
         }
        if protected.intersection(values) and not self.env.context.get("skip_request_lock"):
            if self.filtered(lambda request: request.state != "draft"):
                raise UserError(_("Only draft purchase requests can be edited."))
        if "state" in values and not self.env.context.get("skip_request_workflow"):
            raise AccessError(_("Use the workflow buttons to change the status."))
        return super().write(values)

    def unlink(self):
        if self.filtered(lambda request: request.state != "draft"):
            raise UserError(_("Only draft purchase requests can be deleted."))
        return super().unlink()

    def action_confirm(self):
        for request in self:
            if request.state != "draft":
                raise UserError(_("Only draft purchase requests can be confirmed."))
            if not request.line_ids:
                raise UserError(_("Add at least one purchase request line."))
            if not request.employee_id.department_id:
                raise UserError(_("The requester employee must have a department."))
            request._approval_refresh(replace=True)
            manager_user = request.department_id.manager_id.user_id
            request.with_context(skip_request_workflow=True).write(
                {
                    "state": "waiting_approval",
                    "date_request": fields.Datetime.now(),
                    "date_confirmed": fields.Datetime.now(),
                    "confirmed_by": self.env.user.id,
                    "manager_department": manager_user.id if manager_user else False,
                    "approved_by": False,
                    "date_approved": False,
                    "rejected_by": False,
                    "date_rejected": False,
                    "reject_message": False,
                }
            )
            request.message_post(body=_("Purchase request confirmed and sent for approval."))
        return True

    def action_approve(self):
        if self.filtered(lambda request: request.state != "waiting_approval"):
            raise UserError(_("The purchase request is not waiting for approval."))
        return self._approval_action_approve()

    def _approval_level_approved(self, user, approval):
        for request in self:
            if request.manager_department == user and not request.date_approval_department:
                request.date_approval_department = fields.Datetime.now()
        return True

    def _approval_matrix_approved(self, user):
        self.with_context(skip_request_workflow=True).write(
            {
                "state": "approved",
                "approved_by": user.id,
                "date_approved": fields.Datetime.now(),
            }
        )
        self.message_post(body=_("Purchase request approved."))

    def _approval_matrix_rejected(self, user, reason):
        self.with_context(skip_request_workflow=True).write(
            {
                "state": "reject",
                "rejected_by": user.id,
                "date_rejected": fields.Datetime.now(),
                "reject_message": reason,
            }
        )
        self.message_post(
            body=_("Purchase request rejected by %(user)s. Reason: %(reason)s")
            % {"user": user.display_name, "reason": reason}
        )

    def action_resubmit(self):
        for request in self:
            if request.state != "reject":
                raise UserError(
                    _("Only rejected purchase requests can be resubmitted.")
                )

            request.with_context(
                skip_request_workflow=True
            ).write(
                {
                    "state": "draft",
                    "rejected_by": False,
                    "date_rejected": False,
                    "reject_message": False,
                    "approved_by": False,
                    "date_approved": False,
                }
            )

            request.message_post(
                body=_(
                    "Purchase Request resubmitted and returned to Draft."
                )
            )
    
        return True

    def action_create_rfq(self):
        self.ensure_one()

        selected_lines = self.line_ids.filtered(
            lambda line: line.selected_for_purchase
        )

        if not selected_lines:
            raise UserError(
                _("Please select at least one item to create RFQ.")
            )

        return self._create_purchase_document(
            selected_lines,
            confirm=False,
        )

    def action_create_po(self):
        self.ensure_one()

        selected_lines = self.line_ids.filtered(
            lambda line: line.selected_for_purchase
        )

        if not selected_lines:
            raise UserError(
                _("Please select at least one item to create PO.")
            )

        return self._create_purchase_document(
            selected_lines,
            confirm=True,
        )
    def _create_purchase_document(self, selected_lines, confirm=False):
        self.ensure_one()

        self._validate_for_order()

        if not selected_lines:
            raise UserError(
                _("No selected items found.")
            )

        order = self.env["purchase.order"].create(
            {
                "company_id": self.company_id.id,
                "origin": self.name,
            }
        )

        for line in selected_lines:
            po_line = self.env["purchase.order.line"].create(
                {
                    "order_id": order.id,
                    "product_id": line.product_id.id,
                    "name": line.desc or line.product_id.display_name,
                    "product_qty": line.qty,
                    "product_uom": line.product_uom_id.id,
                    "date_planned": fields.Datetime.now(),
                    "purchase_request_line_id": line.id,
                }
            )

            line.purchase_line_ids = [
                (4, po_line.id)
            ]

        if confirm:
            order.button_confirm()

        return {
            "type": "ir.actions.act_window",
            "name": _("Purchase Order"),
            "res_model": "purchase.order",
            "view_mode": "form",
            "res_id": order.id,
        }

class PurchaseRequestLine(models.Model):
    _name = "purchase.request.line"
    _description = "Purchase Request Line"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "request_eta, id"

    purchase_request_id = fields.Many2one(
        "purchase.request", string="Purchase Request", ondelete="cascade", index=True
    )
    
    selected_for_purchase = fields.Boolean(
        string="Select",
        default=False,
        tracking=True,
    )

    product_id = fields.Many2one(
        "product.product", string="Product", required=True, domain=[("purchase_ok", "=", True)]
    )
    desc = fields.Text(string="Description")
    qty = fields.Float(string="Qty", required=True, default=1.0)
    product_uom_id = fields.Many2one(
        "uom.uom", string="UOM", required=True, compute="_compute_product_fields", store=True,
        readonly=False,
    )
    state = fields.Selection(
        [("draft", "Draft"), ("done", "Done"), ("cancel", "Cancel")],
        default="draft",
        required=True,
        tracking=True,
    )
    request_eta = fields.Date(string="Request ETA", required=True, default=fields.Date.context_today)
    purchase_message = fields.Text(string="Reason For Purchase")

    default_code = fields.Char(string="SKU", compute="_compute_product_fields", store=True)
    origin = fields.Char(string="Reference Number", compute="_compute_release", store=True)
    pr_line_state = fields.Selection(
        related="purchase_request_id.state", string="State PR", store=True
    )
    company_id = fields.Many2one(related="purchase_request_id.company_id", store=True)
    purchase_line_ids = fields.Many2many(
        "purchase.order.line",
        "purchase_request_line_prl_rel",
        "pr_line_id",
        "purchase_line_id",
        string="Purchase Order Lines",
        copy=False,
    )
    qty_released = fields.Float(compute="_compute_release", store=True)
    stock_on_hand = fields.Float(string="Stock On Hand", compute="_compute_stock")
    incoming_qty = fields.Float(string="Incoming", compute="_compute_stock")

    @api.depends("product_id")
    def _compute_product_fields(self):
        for line in self:
            if line.product_id:
                line.default_code = line.product_id.default_code
                line.product_uom_id = line.product_id.uom_id
            else:
                line.default_code = False
                line.product_uom_id = False

    @api.onchange("product_id")
    def _onchange_product_id(self):
        if self.product_id:
            self.desc = self.product_id.display_name
            if not self.purchase_message:
                self.purchase_message = self.purchase_request_id.display_name

    @api.depends("purchase_line_ids.product_qty", "purchase_line_ids.order_id.name", "purchase_line_ids.state")
    def _compute_release(self):
        for line in self:
            valid_lines = line.purchase_line_ids.filtered(lambda po_line: po_line.state != "cancel")
            line.qty_released = sum(valid_lines.mapped("product_qty"))
            line.origin = ", ".join(valid_lines.mapped("order_id.name"))

    @api.depends("product_id.qty_available", "product_id.incoming_qty")
    def _compute_stock(self):
        for line in self:
            line.stock_on_hand = line.product_id.qty_available
            line.incoming_qty = line.product_id.incoming_qty

    @api.constrains("selected_for_purchase")
    def _check_selected_for_purchase(self):
        for line in self:
            if line.selected_for_purchase:
                if line.purchase_request_id.state != "approved":
                    raise ValidationError(
                        _(
                              "Only approved purchase requests can select items for RFQ or PO."
                         )
                    )

    def _validate_for_order(self):
        for line in self:
            if line.purchase_request_id.state != "approved":
                raise UserError(
                    _("Only approved purchase requests can create RFQ or PO.")
                )

            if not line.selected_for_purchase:
                raise UserError(
                    _("Please select the item before creating RFQ or PO.")
                )

            if line.state == "cancel":
                raise UserError(
                    _("Cancelled purchase request lines cannot create RFQ or PO.")
                )

            if line.qty_released >= line.qty:
                raise UserError(
                    _("The selected line has already been fully released.")
                )

    def action_open_create_order_wizard(self):
        self._validate_for_order()
        return {
            "type": "ir.actions.act_window",
            "name": _("Create Purchase Order") if self.env.context.get("pr_confirm_order") else _("Create RFQ"),
            "res_model": "purchase.request.line.make.purchase.order",
            "view_mode": "form",
            "target": "new",
            "context": {
                "active_model": self._name,
                "active_ids": self.ids,
                "default_confirm_order": bool(self.env.context.get("pr_confirm_order")),
            },
        }

    def action_cancel_lines(self):
        self.filtered(lambda line: line.state == "draft").write({"state": "cancel"})
        return True


class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"

    purchase_request_line_id = fields.Many2one(
        "purchase.request.line", string="Purchase Request Line", ondelete="set null", index=True
    )
    purchase_request_line_ids = fields.Many2many(
        "purchase.request.line",
        "purchase_request_line_prl_rel",
        "purchase_line_id",
        "pr_line_id",
        string="Purchase Request Lines",
    )

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        for line in lines:
            if line.purchase_request_line_id:
                line.purchase_request_line_ids = [(4, line.purchase_request_line_id.id)]
        return lines
