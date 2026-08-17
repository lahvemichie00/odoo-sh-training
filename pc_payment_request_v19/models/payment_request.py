from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError


class AccountPaymentMode(models.Model):
    _name = "account.payment.mode"
    _description = "Payment Mode"
    _order = "name"

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)


class PaymentRequestOrder(models.Model):
    _name = "payment.request.order"
    _description = "Payment Request"
    _inherit = ["mail.thread", "mail.activity.mixin", "approval.matrix.mixin"]
    _order = "date_order desc, id desc"
    _check_company_auto = True

    name = fields.Char(
        string="Order Reference",
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _("New"),
        tracking=True,
    )
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("waiting_approval", "Waiting Approval"),
            ("approved", "Approved"),
            ("paid", "Paid"),
            ("rejected", "Rejected"),
        ],
        default="draft",
        required=True,
        copy=False,
        index=True,
        tracking=True,
    )
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company, index=True
    )
    currency_id = fields.Many2one(
        "res.currency",
        required=True,
        default=lambda self: self.env.company.currency_id,
        tracking=True,
    )
    company_currency_id = fields.Many2one(
        related="company_id.currency_id", string="Company Currency", store=True
    )
    user_request_id = fields.Many2one(
        "res.users",
        string="User Request",
        required=True,
        default=lambda self: self.env.user,
        tracking=True,
    )
    department_id = fields.Many2one(
        "hr.department",
        required=True,
        default=lambda self: self._default_department(),
        check_company=True,
        tracking=True,
    )
    journal_id = fields.Many2one(
        "account.journal",
        string="Payment Journal",
        check_company=True,
        domain="[('company_id', '=', company_id), ('type', 'in', ['bank', 'cash'])]",
    )
    date_order = fields.Datetime(
        string="Required Date", required=True, default=fields.Datetime.now, tracking=True
    )
    payment_details = fields.Text(string="Payment Details")
    is_payment_other = fields.Boolean(string="Payment Other")
    payment_mode_id = fields.Many2one(
        "account.payment.mode", string="Payment Mode", required=True, tracking=True
    )
    partner_id = fields.Many2one(
        "res.partner", string="Vendor Name", compute="_compute_totals", store=True
    )
    line_ids = fields.One2many(
        "payment.request.order.line", "order_id", string="Payment Request Line", copy=True
    )
    amount_lines_total = fields.Monetary(
        string="Payment Amount", compute="_compute_totals", store=True, tracking=True
    )
    amount_currency = fields.Monetary(
        string="Base Currency Amount",
        currency_field="company_currency_id",
        compute="_compute_totals",
        store=True,
    )
    is_locked = fields.Boolean(
        string="Locked",
        default=False,
        tracking=True,
    )
    submitted_by_id = fields.Many2one("res.users", string="Submitted By", readonly=True)
    approved_by_id = fields.Many2one("res.users", string="Approved By", readonly=True)
    rejected_by_id = fields.Many2one("res.users", string="Rejected By", readonly=True)
    date_submitted = fields.Datetime(string="Submitted Date", readonly=True)
    date_approved = fields.Datetime(string="Approved Date", readonly=True)
    date_rejected = fields.Datetime(string="Rejected Date", readonly=True)
    reject_reason = fields.Text(string="Reject Reason", readonly=True)
    payment_ids = fields.One2many(
        "account.payment", "payment_request_id", string="Payment Vouchers", readonly=True
    )
    payment_voucher = fields.Boolean(
        string="Payment Voucher", compute="_compute_payment_voucher"
    )

    @api.model
    def _default_department(self, user=None, company=None):
        user = user or self.env.user
        company = company or self.env.company
        employee = self.env["hr.employee"].sudo().search(
            [("user_id", "=", user.id), ("company_id", "=", company.id)], limit=1
        )
        return employee.department_id

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
                    .next_by_code("payment.request.order")
                    or _("New")
                )
            values.setdefault("currency_id", company.currency_id.id)
            if not values.get("department_id"):
                user = self.env["res.users"].browse(
                    values.get("user_request_id") or self.env.user.id
                )
                department = self._default_department(user, company)
                if department:
                    values["department_id"] = department.id
            if not self.env.context.get("payment_request_migration"):
                values["state"] = "draft"
        return super().create(vals_list)

    @api.onchange("user_request_id", "company_id")
    def _onchange_requester(self):
        department = self._default_department(self.user_request_id, self.company_id)
        if department:
            self.department_id = department
        if self.company_id:
            self.currency_id = self.company_id.currency_id

    @api.depends(
        "line_ids.amount", "line_ids.partner_id", "currency_id", "company_id", "date_order"
    )
    def _compute_totals(self):
        for request in self:
            request.amount_lines_total = sum(request.line_ids.mapped("amount"))
            request.partner_id = request.line_ids[:1].partner_id
            conversion_date = fields.Date.to_date(request.date_order) or fields.Date.context_today(request)
            if request.currency_id and request.company_id:
                request.amount_currency = request.currency_id._convert(
                    request.amount_lines_total,
                    request.company_id.currency_id,
                    request.company_id,
                    conversion_date,
                )
            else:
                request.amount_currency = request.amount_lines_total

    @api.depends("payment_ids.state")
    def _compute_payment_voucher(self):
        for request in self:
            request.payment_voucher = bool(
                request.payment_ids.filtered(
                    lambda payment: payment.state not in ("draft", "cancel", "canceled")
                )
            )

    @api.constrains("line_ids", "amount_lines_total")
    def _check_amount(self):
        for request in self:
            if request.line_ids and request.amount_lines_total <= 0:
                raise ValidationError(_("Payment amount must be greater than zero."))

    def write(self, values):
        protected = {
            "company_id", "currency_id", "user_request_id", "department_id",
            "journal_id", "date_order", "payment_details", "is_payment_other",
            "payment_mode_id", "line_ids",
        }

        if protected.intersection(values) and not self.env.context.get("skip_request_lock"):
            if self.filtered(lambda request: request.is_locked):
                raise UserError(_("Payment request is locked and cannot be edited."))

        if "state" in values and not self.env.context.get("skip_request_workflow"):
            raise AccessError(_("Use the workflow buttons to change the status."))

        return super().write(values)

    def unlink(self):
        if self.filtered(lambda request: request.state != "draft"):
            raise UserError(_("Only draft payment requests can be deleted."))
        return super().unlink()

    def action_submit(self):
        for request in self:
            if request.state != "draft":
                raise UserError(_("Only draft payment requests can be submitted."))

            if not request.line_ids:
                raise UserError(_("Add at least one payment request line."))

            if request.line_ids.filtered(lambda line: line.amount <= 0):
                raise UserError(_("Every payment request line must have a positive amount."))

            request._approval_refresh(replace=True)

            request.with_context(skip_request_workflow=True).write(
                {
                    "state": "waiting_approval",
                    "is_locked": True,
                    "submitted_by_id": self.env.user.id,
                    "date_submitted": fields.Datetime.now(),
                    "approved_by_id": False,
                    "date_approved": False,
                    "rejected_by_id": False,
                    "date_rejected": False,
                    "reject_reason": False,
                }
            )

            request.message_post(
                body=_("Payment request submitted for approval.")
            )

        return True 

    def action_toggle_lock(self):
        for request in self:
            if request.user_request_id != self.env.user:
                raise UserError(
                    _("Only the requester can lock or unlock this payment request.")
                )

            if request.is_locked:
                request.write({
                    "is_locked": False,
                })

                request.message_post(
                    body=_(
                        "Payment request unlocked by %(user)s for correction."
                    )
                    % {
                        "user": self.env.user.name,
                    }
                )

            else:
                request._approval_refresh(replace=True)

                request.with_context(skip_request_workflow=True).write(
                    {
                        "state": "waiting_approval",
                        "is_locked": True,
                        "submitted_by_id": self.env.user.id,
                        "date_submitted": fields.Datetime.now(),
                        "approved_by_id": False,
                        "date_approved": False,
                        "rejected_by_id": False,
                        "date_rejected": False,
                        "reject_reason": False,
                    }
                )

                request.message_post(
                    body=_(
                        "Payment request locked and sent for approval by %(user)s."
                    )
                    % {
                        "user": self.env.user.name,
                    }
                )

        return True

    def action_approve(self):
        if self.filtered(lambda request: request.state != "waiting_approval"):
            raise UserError(
                _("The payment request is not waiting for approval.")
            )

        return self._approval_action_approve()


    def action_register_payment(self):
        self.ensure_one()

        if self.state != "approved":
            raise UserError(
                _("Only approved payment requests can register payment.")
            )

        if not self.journal_id:
            raise UserError(
                _("Please select a Payment Journal before registering payment.")
            )

        payment = self.env["account.payment"].create(
            {
                "payment_type": "outbound",
                "partner_type": "supplier",
                "partner_id": self.partner_id.id,
                "amount": self.amount_lines_total,
                "currency_id": self.currency_id.id,
                "journal_id": self.journal_id.id,
                "payment_request_id": self.id,
                "date": fields.Date.today(),
            }
        )

        return {
            "type": "ir.actions.act_window",
            "name": _("Payment"),
            "res_model": "account.payment",
            "view_mode": "form",
            "res_id": payment.id,
        }

    def _approval_matrix_approved(self, user):
        self.with_context(skip_request_workflow=True).write(
            {
                "state": "approved",
                "approved_by_id": user.id,
                "date_approved": fields.Datetime.now(),
            }
        )
        
        self.message_post(
            body=_(
                "Payment request approved by %(user)s."
            )
            % {
                "user": user.name,
            }
        )

    def _approval_matrix_rejected(self, user, reason):
        self.with_context(skip_request_workflow=True).write(
            {
                "state": "rejected",
                "rejected_by_id": user.id,
                "date_rejected": fields.Datetime.now(),
                "reject_reason": reason,
            }
        )
        self.message_post(
            body=_("Payment request rejected by %(user)s. Reason: %(reason)s")
            % {"user": user.display_name, "reason": reason}
        )

    def _mark_paid_from_payment(self):
        approved = self.filtered(lambda request: request.state == "approved")
        approved.with_context(skip_request_workflow=True).write({"state": "paid"})
        for request in approved:
            request.message_post(body=_("Payment request marked as paid by a posted payment."))


class PaymentRequestOrderLine(models.Model):
    _name = "payment.request.order.line"
    _description = "Payment Request Line"
    _order = "id"
    _check_company_auto = True

    name = fields.Char(default=lambda self: _("Payment"))
    order_id = fields.Many2one(
        "payment.request.order", required=True, ondelete="cascade", index=True
    )
    company_id = fields.Many2one(related="order_id.company_id", store=True)
    currency_id = fields.Many2one(related="order_id.currency_id", store=True)
    partner_id = fields.Many2one(
        "res.partner", string="Vendor Name", required=True, domain=[("supplier_rank", ">", 0)]
    )
    res_partner_bank_id = fields.Many2one(
        "res.partner.bank",
        string="Vendor Bank Acc No",
        domain="[('partner_id', '=', partner_id)]",
    )
    bank_id = fields.Many2one("res.bank", string="Vendor Bank")
    bic = fields.Char(string="Bank Identifier Code")
    routing_no = fields.Char(string="Routing No")
    bank_address = fields.Text(string="Bank Address")
    amount = fields.Monetary(string="Payment Amount", required=True)
    account_id = fields.Many2one("account.account", string="Account", check_company=True)
    analytic_account_id = fields.Many2one(
        "account.analytic.account", string="Analytic Account", check_company=True
    )
    is_payment_other = fields.Boolean(string="Is Payment Other")

    @api.onchange("res_partner_bank_id")
    def _onchange_partner_bank(self):
        if self.res_partner_bank_id:
            self.bank_id = self.res_partner_bank_id.bank_id
            self.bic = self.res_partner_bank_id.bank_bic
            bank = self.res_partner_bank_id.bank_id
            self.bank_address = ", ".join(
                filter(None, [bank.street, bank.street2, bank.city, bank.zip])
            )


class AccountPayment(models.Model):
    _inherit = "account.payment"

    payment_request_id = fields.Many2one(
        "payment.request.order", string="Payment Request", ondelete="set null", index=True
    )

    def action_post(self):
        result = super().action_post()
        self.mapped("payment_request_id")._mark_paid_from_payment()
        return result
