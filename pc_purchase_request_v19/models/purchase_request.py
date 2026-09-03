import logging

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

_logger = logging.getLogger(__name__)


class ProductTemplate(models.Model):
    _inherit = "product.template"


class PurchaseRequest(models.Model):
    _name = "purchase.request"
    _description = "Purchase Request"
    _inherit = [
        "mail.thread",
        "mail.activity.mixin",
        "approval.matrix.mixin",
    ]
    _order = "date_order desc, id desc"
    _check_company_auto = True

    # ==========================================================
    # BASIC INFORMATION
    # ==========================================================

    name = fields.Char(
        string="Reference",
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _("New"),
        tracking=True,
    )

    date_order = fields.Datetime(
        string="Date",
        default=fields.Datetime.now,
        required=True,
    )

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

    group_category_id = fields.Many2one(
        "product.group.category",
        string="Group Category",
        tracking=True,
    )

    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )

    # ==========================================================
    # PURCHASE REQUEST STATUS
    # ==========================================================

    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("waiting_approval", "Waiting Approval"),
            ("approved", "Approved"),
            ("reject", "Reject"),
            ("cancelled", "Cancelled"),
            ("completed", "Completed"),
        ],
        default="draft",
        required=True,
        copy=False,
        tracking=True,
        index=True,
    )

    # ==========================================================
    # PROCESS INFORMATION
    # ==========================================================

    is_over_process = fields.Boolean(
        string="Over Process",
        readonly=True,
    )

    date_request = fields.Datetime(
        string="Requestion Date",
        readonly=True,
    )

    date_confirmed = fields.Datetime(
        string="Confirmed Date",
        readonly=True,
    )

    confirmed_by = fields.Many2one(
        "res.users",
        string="Confirmed By",
        readonly=True,
    )

    manager_department = fields.Many2one(
        "res.users",
        string="Department Manager",
        readonly=True,
    )

    date_approval_department = fields.Datetime(
        string="Department Approval Date",
        readonly=True,
    )

    approved_by = fields.Many2one(
        "res.users",
        string="Approved By",
        readonly=True,
    )

    date_approved = fields.Datetime(
        string="Approved Date",
        readonly=True,
    )

    rejected_by = fields.Many2one(
        "res.users",
        string="Rejected By",
        readonly=True,
    )

    date_rejected = fields.Datetime(
        string="Rejected Date",
        readonly=True,
    )

    reject_message = fields.Text(
        string="Reject Reason",
        readonly=True,
    )

    # ==========================================================
    # CANCELLATION
    # ==========================================================

    cancellation_reason = fields.Text(
        string="Cancellation Reason",
        readonly=True,
        copy=False,
        tracking=True,
    )

    cancelled_by = fields.Many2one(
        "res.users",
        string="Cancelled By",
        readonly=True,
        copy=False,
        tracking=True,
    )

    date_cancelled = fields.Datetime(
        string="Cancelled Date",
        readonly=True,
        copy=False,
        tracking=True,
    )

    # ==========================================================
    # PURCHASE REQUEST LINES
    # ==========================================================

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
        compute="_compute_is_locked",
    )

    # ==========================================================
    # SMART BUTTON COUNTS
    # ==========================================================

    rfq_count = fields.Integer(
        string="RFQs",
        compute="_compute_purchase_document_counts",
    )

    po_count = fields.Integer(
        string="Purchase Orders",
        compute="_compute_purchase_document_counts",
    )

    # ==========================================================
    # DEFAULT EMPLOYEE
    # ==========================================================

    @api.model
    def _default_employee(self, user=None, company=None):
        user = user or self.env.user
        company = company or self.env.company

        return self.env["hr.employee"].sudo().search(
            [
                ("user_id", "=", user.id),
                ("company_id", "=", company.id),
            ],
            limit=1,
        )

    # ==========================================================
    # CREATE
    # ==========================================================

    @api.model_create_multi
    def create(self, vals_list):

        for values in vals_list:

            company = self.env["res.company"].browse(
                values.get("company_id")
                or self.env.company.id
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
                    self.env["res.users"].browse(
                        values.get("user_id")
                        or self.env.user.id
                    ),
                    company,
                )

                if employee:
                    values["employee_id"] = employee.id

            if not self.env.context.get(
                "purchase_request_migration"
            ):
                values["state"] = "draft"

        return super().create(vals_list)

    # ==========================================================
    # ONCHANGE
    # ==========================================================

    @api.onchange("user_id", "company_id")
    def _onchange_user(self):

        employee = self._default_employee(
            self.user_id,
            self.company_id,
        )

        if employee:
            self.employee_id = employee

    # ==========================================================
    # COMPUTE TOTAL
    # ==========================================================

    @api.depends("line_ids.qty")
    def _compute_total_qty(self):

        for request in self:
            request.total_qty = sum(
                request.line_ids.mapped("qty")
            )

    # ==========================================================
    # COMPUTE LOCK
    # ==========================================================

    @api.depends("state")
    def _compute_is_locked(self):

        for request in self:
            request.is_locked = request.state not in (
                "draft",
                "reject",
            )

    # ==========================================================
    # SMART BUTTON COUNTS
    # ==========================================================

    def _compute_purchase_document_counts(self):

        PurchaseLine = self.env["purchase.order.line"]

        for request in self:

            lines = PurchaseLine.search(
                [
                    (
                        "purchase_request_line_id",
                        "in",
                        request.line_ids.ids,
                    ),
                ]
            )

            orders = lines.mapped("order_id")

            request.rfq_count = len(
                orders.filtered(
                    lambda order:
                    order.approval_stage == "rfq"
                )
            )

            request.po_count = len(
                orders.filtered(
                    lambda order:
                    order.approval_stage == "po"
                )
            )

    # ==========================================================
    # OPEN RFQs
    # ==========================================================

    def action_open_rfqs(self):

        self.ensure_one()

        orders = self.env["purchase.order"].search(
            [
                (
                    "order_line.purchase_request_line_id",
                    "in",
                    self.line_ids.ids,
                ),
                ("approval_stage", "=", "rfq"),
            ]
        )

        return {
            "type": "ir.actions.act_window",
            "name": _("Requests for Quotation"),
            "res_model": "purchase.order",
            "view_mode": "list,form",
            "domain": [
                ("id", "in", orders.ids),
            ],
            "target": "current",
        }

    # ==========================================================
    # OPEN PURCHASE ORDERS
    # ==========================================================

    def action_open_purchase_orders(self):

        self.ensure_one()

        orders = self.env["purchase.order"].search(
            [
                (
                    "order_line.purchase_request_line_id",
                    "in",
                    self.line_ids.ids,
                ),
                ("approval_stage", "=", "po"),
            ]
        )

        return {
            "type": "ir.actions.act_window",
            "name": _("Purchase Orders"),
            "res_model": "purchase.order",
            "view_mode": "list,form",
            "domain": [
                ("id", "in", orders.ids),
            ],
            "target": "current",
        }

    # ==========================================================
    # VALIDATE LINE QUANTITY
    # ==========================================================

    @api.constrains("line_ids.qty")
    def _check_line_quantity(self):

        for request in self:

            if request.line_ids.filtered(
                lambda line: line.qty <= 0
            ):
                raise ValidationError(
                    _(
                        "Purchase request quantities "
                        "must be positive."
                    )
                )

    # ==========================================================
    # WRITE
    # ==========================================================

    def write(self, values):

        protected = {
            "date_order",
            "user_id",
            "employee_id",
            "company_id",
            "group_category_id",
        }

        if (
            protected.intersection(values)
            and not self.env.context.get(
                "skip_request_lock"
            )
        ):

            if self.filtered(
                lambda request:
                request.state not in (
                    "draft",
                    "reject",
                )
            ):

                _logger.warning(
                    "PURCHASE REQUEST LOCK BLOCKED. "
                    "VALUES=%s CONTEXT=%s",
                    values,
                    self.env.context,
                )

                raise UserError(
                    _(
                        "Only draft or rejected purchase "
                        "requests can be edited."
                    )
                )

        if (
            "state" in values
            and not self.env.context.get(
                "skip_request_workflow"
            )
        ):
            raise AccessError(
                _(
                    "Use the workflow buttons "
                    "to change the status."
                )
            )

        return super().write(values)

    # ==========================================================
    # DELETE
    # ==========================================================

    def unlink(self):

        if self.filtered(
            lambda request:
            request.state != "draft"
        ):
            raise UserError(
                _(
                    "Only draft purchase requests "
                    "can be deleted."
                )
            )

        return super().unlink()

    # ==========================================================
    # CONFIRM / SUBMIT
    # ==========================================================

    def action_confirm(self):

        for request in self:

            if request.state != "draft":
                raise UserError(
                    _(
                        "Only draft purchase requests "
                        "can be confirmed."
                    )
                )

            if not request.line_ids:
                raise UserError(
                    _(
                        "Add at least one purchase "
                        "request line."
                    )
                )

            if not request.employee_id.department_id:
                raise UserError(
                    _(
                        "The requester employee must "
                        "have a department."
                    )
                )

            request._approval_refresh(
                replace=True
            )

            manager_user = (
                request.department_id
                .manager_id
                .user_id
            )

            request.with_context(
                skip_request_workflow=True
            ).write(
                {
                    "state": "waiting_approval",
                    "date_request": fields.Datetime.now(),
                    "date_confirmed": fields.Datetime.now(),
                    "confirmed_by": self.env.user.id,
                    "manager_department": (
                        manager_user.id
                        if manager_user
                        else False
                    ),
                    "approved_by": False,
                    "date_approved": False,
                    "rejected_by": False,
                    "date_rejected": False,
                    "reject_message": False,
                    "cancelled_by": False,
                    "date_cancelled": False,
                    "cancellation_reason": False,
                }
            )

            request.message_post(
                body=_(
                    "Purchase request confirmed "
                    "and sent for approval."
                )
            )

        return True

    # ==========================================================
    # APPROVE
    # ==========================================================

    def action_approve(self):

        if self.filtered(
            lambda request:
            request.state != "waiting_approval"
        ):
            raise UserError(
                _(
                    "The purchase request is not "
                    "waiting for approval."
                )
            )

        return self._approval_action_approve()

    # ==========================================================
    # APPROVAL LEVEL
    # ==========================================================

    def _approval_level_approved(
        self,
        user,
        approval,
    ):

        for request in self:

            if (
                request.manager_department == user
                and not request.date_approval_department
            ):

                request.date_approval_department = (
                    fields.Datetime.now()
                )

        return True

    # ==========================================================
    # APPROVAL COMPLETED
    # ==========================================================

    def _approval_matrix_approved(self, user):

        self.with_context(
            skip_request_workflow=True
        ).write(
            {
                "state": "approved",
                "approved_by": user.id,
                "date_approved": fields.Datetime.now(),
            }
        )

        self.message_post(
            body=_(
                "Purchase request approved."
            )
        )

    # ==========================================================
    # APPROVAL REJECTED
    # ==========================================================

    def _approval_matrix_rejected(
        self,
        user,
        reason,
    ):

        self.with_context(
            skip_request_workflow=True
        ).write(
            {
                "state": "reject",
                "rejected_by": user.id,
                "date_rejected": fields.Datetime.now(),
                "reject_message": reason,
            }
        )

        self.message_post(
            body=_(
                "Purchase request rejected by "
                "%(user)s. Reason: %(reason)s"
            )
            % {
                "user": user.display_name,
                "reason": reason,
            }
        )

    # ==========================================================
    # RESUBMIT REJECTED REQUEST
    # ==========================================================

    def action_resubmit(self):

        for request in self:

            if request.state != "reject":
                raise UserError(
                    _(
                        "Only rejected purchase requests "
                        "can be resubmitted."
                    )
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
                    "cancelled_by": False,
                    "date_cancelled": False,
                    "cancellation_reason": False,
                }
            )

            request.message_post(
                body=_(
                    "Purchase Request resubmitted "
                    "and returned to Draft."
                )
            )

        return True

    # ==========================================================
    # OPEN CANCEL WIZARD
    # ==========================================================

    def action_open_cancel_wizard(self):

        self.ensure_one()

        if self.state not in (
            "draft",
            "waiting_approval",
            "approved",
        ):
            raise UserError(
                _(
                    "Only Draft, Waiting Approval "
                    "or Approved purchase requests "
                    "can be cancelled."
                )
            )

        return {
            "type": "ir.actions.act_window",
            "name": _("Cancel Purchase Request"),
            "res_model": "purchase.request.cancel.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_purchase_request_id": self.id,
            },
        }

    # ==========================================================
    # CANCEL
    # ==========================================================

    def action_cancel(self, reason=False):

        for request in self:

            if request.state not in (
                "draft",
                "waiting_approval",
                "approved",
            ):
                raise UserError(
                    _(
                        "Only Draft, Waiting Approval "
                        "or Approved purchase requests "
                        "can be cancelled."
                    )
                )

            if not reason:
                raise UserError(
                    _(
                        "Please provide a cancellation reason."
                    )
                )

            request.with_context(
                skip_request_workflow=True
            ).write(
                {
                    "state": "cancelled",
                    "cancellation_reason": reason,
                    "cancelled_by": self.env.user.id,
                    "date_cancelled": (
                        fields.Datetime.now()
                    ),
                }
            )

            request.message_post(
                body=_(
                    "Purchase request cancelled by "
                    "%(user)s. Reason: %(reason)s"
                )
                % {
                    "user": self.env.user.display_name,
                    "reason": reason,
                }
            )

        return True


    # ==========================================================
    # CHECK COMPLETED
    # ==========================================================

    def _check_completed(self):

        for request in self:

            if request.state != "approved":
                continue

            if not request.line_ids:
                continue

            completed_lines = request.line_ids.filtered(
                lambda line: line.state == "done"
            )

            if len(completed_lines) == len(request.line_ids):

                request.with_context(
                    skip_request_workflow=True
                ).write(
                    {
                        "state": "completed",
                    }
                )

                request.message_post(
                    body=_(
                        "Purchase Request completed."
                    )
                )

        return True

    # ==========================================================
    # CREATE RFQ
    # ==========================================================

    def action_create_rfq(self):

        self.ensure_one()

        if self.state != "approved":
            raise UserError(
                _(
                    "Only approved Purchase Requests "
                    "can create RFQ."
                )
            )

        selected_lines = self.line_ids.filtered(
            lambda line:
            line.selected_for_purchase
        )

        if not selected_lines:
            raise UserError(
                _(
                    "Please select at least one item "
                    "to create RFQ."
                )
            )

        used_lines = selected_lines.filtered(
            lambda line:
            line.state == "done"
            or line.is_purchased
        )

        if used_lines:
            raise UserError(
                _(
                    "One or more selected items "
                    "have already been used."
                )
            )

        return self._create_purchase_document(
            selected_lines,
            confirm=False,
        )

    # ==========================================================
    # CREATE PO
    # ==========================================================

    def action_create_po(self):

        self.ensure_one()

        if self.state != "approved":
            raise UserError(
                _(
                    "Only approved Purchase Requests "
                    "can create Purchase Orders."
                )
            )

        selected_lines = self.line_ids.filtered(
            lambda line:
            line.selected_for_purchase
        )

        if not selected_lines:
            raise UserError(
                _(
                    "Please select at least one item "
                    "to create Purchase Order."
                )
            )

        used_lines = selected_lines.filtered(
            lambda line:
            line.state == "done"
            or line.is_purchased
        )

        if used_lines:
            raise UserError(
                _(
                    "One or more selected items "
                    "have already been used."
                )
            )

        return self._create_purchase_document(
            selected_lines,
            confirm=True,
        )

    # ==========================================================
    # CREATE PURCHASE DOCUMENT FROM PR
    # ==========================================================

    def _create_purchase_document(
        self,
        selected_lines,
        confirm=False,
    ):

        self.ensure_one()

        if not selected_lines:
            raise UserError(
                _("No selected items found.")
            )

        for line in selected_lines:
            line._validate_for_order()

        order_lines = []

        for line in selected_lines:

            product_uom = (
                line.product_uom_id
                or line.product_id.uom_id
            )

            if not product_uom:
                raise UserError(
                    _(
                        "No UOM is defined for product %s."
                    )
                    % line.product_id.display_name
                )

            order_lines.append(
                (
                    0,
                    0,
                    {
                        "product_id": line.product_id.id,
                        "name": (
                            line.desc
                            or line.product_id.display_name
                        ),
                        "product_qty": line.qty,
                        "product_uom_id": product_uom.id,
                        "date_planned": fields.Datetime.now(),
                        "purchase_request_line_id": line.id,
                    },
                )
            )

        return {
            "type": "ir.actions.act_window",
            "name": (
                _("Purchase Order")
                if confirm
                else _("Request for Quotation")
            ),
            "res_model": "purchase.order",
            "view_mode": "form",
            "target": "current",
            "context": {
                "default_origin": self.name,
                "default_company_id": self.company_id.id,
                "default_order_line": order_lines,

                "from_purchase_request": True,

                "default_approval_stage": (
                    "po"
                    if confirm
                    else "rfq"
                ),

                "default_approval_state": "draft",

                "pr_confirm_order": confirm,
                "default_confirm_order": confirm,
            },
        }

# =================================================================
# PURCHASE REQUEST LINE
# =================================================================


class PurchaseRequestLine(models.Model):

    _name = "purchase.request.line"
    _description = "Purchase Request Line"
    _inherit = [
        "mail.thread",
        "mail.activity.mixin",
    ]
    _order = "request_eta, id"

    # ==========================================================
    # BASIC
    # ==========================================================

    purchase_request_id = fields.Many2one(
        "purchase.request",
        string="Purchase Request",
        ondelete="cascade",
        index=True,
    )

    selected_for_purchase = fields.Boolean(
        string="Select",
        default=False,
        tracking=True,
    )

    is_purchased = fields.Boolean(
        string="Already Used",
        compute="_compute_is_purchased",
    )

    @api.depends(
        "purchase_line_ids",
        "purchase_line_ids.order_id",
    )
    def _compute_is_purchased(self):

        for line in self:
            line.is_purchased = bool(
                line.purchase_line_ids
            )

    product_id = fields.Many2one(
        "product.product",
        string="Product",
        required=True,
        domain=[
            ("purchase_ok", "=", True)
        ],
    )

    desc = fields.Text(
        string="Description",
    )

    qty = fields.Float(
        string="Qty",
        required=True,
        default=1.0,
    )

    product_uom_id = fields.Many2one(
        "uom.uom",
        string="UOM",
        compute="_compute_product_fields",
        store=True,
        readonly=False,
    )

    request_eta = fields.Date(
        string="Request ETA",
        required=True,
        default=fields.Date.context_today,
    )

    purchase_message = fields.Text(
        string="Reason For Purchase",
    )

    default_code = fields.Char(
        string="SKU",
        compute="_compute_product_fields",
        store=True,
    )

    # ==========================================================
    # LINE STATUS
    # ==========================================================

    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("done", "Done"),
            ("cancel", "Cancel"),
        ],
        default="draft",
        required=True,
        tracking=True,
    )

    pr_line_state = fields.Selection(
        related="purchase_request_id.state",
        string="State PR",
        store=True,
    )

    # ==========================================================
    # COMPANY
    # ==========================================================

    company_id = fields.Many2one(
        related="purchase_request_id.company_id",
        store=True,
    )

    # ==========================================================
    # PURCHASE DOCUMENT RELATION
    # ==========================================================

    purchase_line_ids = fields.One2many(
        "purchase.order.line",
        "purchase_request_line_id",
        string="Purchase Order Lines",
        copy=False,
    )

    # ==========================================================
    # STOCK
    # ==========================================================

    stock_on_hand = fields.Float(
        string="Stock On Hand",
        compute="_compute_stock",
    )

    incoming_qty = fields.Float(
        string="Incoming",
        compute="_compute_stock",
    )

    # ==========================================================
    # CREATE
    # ==========================================================

    @api.model_create_multi
    def create(self, vals_list):

        for vals in vals_list:

            product_id = vals.get("product_id")

            # --------------------------------------------------
            # Automatically set UOM from Product
            # --------------------------------------------------

            if (
                product_id
                and not vals.get("product_uom_id")
            ):

                product = self.env[
                    "product.product"
                ].browse(product_id)

                if (
                    product.exists()
                    and product.uom_id
                ):
                    vals["product_uom_id"] = (
                        product.uom_id.id
                    )

        return super().create(vals_list)

    # ==========================================================
    # PRODUCT COMPUTE
    # ==========================================================

    @api.depends("product_id")
    def _compute_product_fields(self):

        for line in self:

            if line.product_id:

                line.default_code = (
                    line.product_id.default_code
                )

                if not line.product_uom_id:
                    line.product_uom_id = (
                        line.product_id.uom_id
                    )
            else:

                line.default_code = False
                line.product_uom_id = False

    # ==========================================================
    # PRODUCT ONCHANGE
    # ==========================================================

    @api.onchange("product_id")
    def _onchange_product_id(self):

        if self.product_id:

            self.desc = (
                self.product_id.display_name
            )

            # --------------------------------------------------
            # Automatically set UOM in the form
            # --------------------------------------------------

            self.product_uom_id = (
                self.product_id.uom_id
            )

            if not self.purchase_message:

                self.purchase_message = (
                    self.purchase_request_id
                    .display_name
                )

    # ==========================================================
    # STOCK COMPUTATION
    # ==========================================================

    @api.depends(
        "product_id.qty_available",
        "product_id.incoming_qty",
    )
    def _compute_stock(self):

        for line in self:

            line.stock_on_hand = (
                line.product_id.qty_available
            )

            line.incoming_qty = (
                line.product_id.incoming_qty
            )

        # ==========================================================
    # SELECTION VALIDATION
    # ==========================================================

    @api.constrains("selected_for_purchase")
    def _check_selected_for_purchase(self):

        for line in self:

            if not line.selected_for_purchase:
                continue

            if (
                line.purchase_request_id.state
                != "approved"
            ):
                raise ValidationError(
                    _(
                        "Only approved Purchase Requests "
                        "can select items for RFQ or PO."
                    )
                )

            if (
                line.state == "done"
                or line.is_purchased
            ):
                raise ValidationError(
                    _(
                        "This item has already been used "
                        "for RFQ or PO."
                    )
                )

            if line.state == "cancel":
                raise ValidationError(
                    _(
                        "Cancelled items cannot be selected."
                    )
                )

        # ==========================================================
    # VALIDATE FOR RFQ / PO
    # ==========================================================

    def _validate_for_order(self):

        for line in self:

            if (
                line.purchase_request_id.state
                != "approved"
            ):
                raise UserError(
                    _(
                        "Only approved Purchase Requests "
                        "can create RFQ or PO."
                    )
                )

            if not line.selected_for_purchase:
                raise UserError(
                    _(
                        "Please select the item before "
                        "creating RFQ or PO."
                    )
                )

            if line.state == "cancel":
                raise UserError(
                    _(
                        "Cancelled Purchase Request "
                        "lines cannot create RFQ or PO."
                    )
                )

            if (
                line.state == "done"
                or line.is_purchased
            ):
                raise UserError(
                    _(
                        "This item has already been used "
                        "for RFQ or PO."
                    )
                )

            if (
                not line.product_uom_id
                and not line.product_id.uom_id
            ):
                raise UserError(
                    _(
                        "No UOM is defined for product %s."
                    )
                    % line.product_id.display_name
                )

        return True

    # ==========================================================
    # OPEN CREATE ORDER WIZARD
    # ==========================================================

    def action_open_create_order_wizard(self):

        self._validate_for_order()

        return {
            "type": "ir.actions.act_window",
            "name": (
                _("Create Purchase Order")
                if self.env.context.get(
                    "pr_confirm_order"
                )
                else _("Create RFQ")
            ),
            "res_model": (
                "purchase.request.line."
                "make.purchase.order"
            ),
            "view_mode": "form",
            "target": "new",
            "context": {
                "active_model": self._name,
                "active_ids": self.ids,
                "default_confirm_order": bool(
                    self.env.context.get(
                        "pr_confirm_order"
                    )
                ),
            },
        }

    # ==========================================================
    # CANCEL LINE
    # ==========================================================

    def action_cancel_lines(self):

        self.filtered(
            lambda line:
            line.state == "draft"
        ).write(
            {
                "state": "cancel",
            }
        )

        return True
    
# ==========================================================
# LOCK COMPLETED PURCHASE REQUEST LINE
# ==========================================================

def write(self, vals):

    protected_fields = {
        "product_id",
        "desc",
        "qty",
        "product_uom_id",
        "request_eta",
        "purchase_message",
        "selected_for_purchase",
    }


    if (
        protected_fields.intersection(vals)
        and not self.env.context.get(
            "skip_pr_line_lock"
        )
    ):

        locked_lines = self.filtered(
            lambda line:
            line.state == "done"
        )


        if locked_lines:

            raise UserError(
                _(
                    "Completed Purchase Request "
                    "items cannot be edited or reused."
                )
            )


    return super().write(vals)

# ==========================================================
# PURCHASE ORDER LINE
# ==========================================================


class PurchaseOrderLine(models.Model):

    _inherit = "purchase.order.line"


    purchase_request_line_id = fields.Many2one(
        "purchase.request.line",
        string="Purchase Request Line",
        ondelete="set null",
        index=True,
        copy=False,
    )


    # ==========================================================
    # CREATE PURCHASE ORDER LINE
    # ==========================================================

    @api.model_create_multi
    def create(self, vals_list):

        lines = super().create(vals_list)

        pr_lines = lines.mapped(
            "purchase_request_line_id"
        )

        if pr_lines:

            pr_lines.with_context(
                skip_pr_line_lock=True
            ).write(
                {
                    "selected_for_purchase": False,
                    "state": "done",
                }
            )

            requests = pr_lines.mapped(
                "purchase_request_id"
            )

            requests._check_completed()

        return lines


    # ==========================================================
    # LOCK COMPLETED LINE
    # ==========================================================

    def write(self, vals):

        protected_fields = {
            "product_id",
            "desc",
            "qty",
            "product_uom_id",
            "request_eta",
            "purchase_message",
            "selected_for_purchase",
        }

        if (
            protected_fields.intersection(vals)
            and not self.env.context.get(
                "skip_pr_line_lock"
            )
        ):

            if self.filtered(
                lambda line:
                line.state == "done"
            ):
                raise UserError(
                    _(
                        "Completed Purchase Request "
                        "items cannot be edited or reused."
                    )
                )

        return super().write(vals)
    