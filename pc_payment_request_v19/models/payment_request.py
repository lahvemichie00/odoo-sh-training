from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError


class PcPaymentRequest(models.Model):
    _name = "pc.payment.request"
    _description = "Payment Request"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "create_date desc, id desc"
    _check_company_auto = True

    name = fields.Char(
        string="Request Reference",
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
            ("cancelled", "Cancelled"),
        ],
        default="draft",
        required=True,
        copy=False,
        index=True,
        tracking=True,
    )
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    currency_id = fields.Many2one(
        "res.currency",
        required=True,
        default=lambda self: self.env.company.currency_id,
        tracking=True,
    )
    company_currency_id = fields.Many2one(
        related="company_id.currency_id",
        store=True,
        readonly=True,
    )
    requester_id = fields.Many2one(
        "res.users",
        string="Requester",
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
    partner_id = fields.Many2one(
        "res.partner",
        string="Vendor / Payee",
        required=True,
        tracking=True,
    )
    journal_id = fields.Many2one(
        "account.journal",
        string="Payment Journal",
        check_company=True,
        domain="[('company_id', '=', company_id), ('type', 'in', ('bank', 'cash'))]",
        tracking=True,
    )
    payment_method = fields.Selection(
        [
            ("bank_transfer", "Bank Transfer"),
            ("cash", "Cash"),
            ("cheque", "Cheque"),
            ("other", "Other"),
        ],
        default="bank_transfer",
        required=True,
        tracking=True,
    )
    required_date = fields.Date(
        required=True,
        default=fields.Date.context_today,
        tracking=True,
    )
    payment_details = fields.Text(required=True)
    is_payment_other = fields.Boolean(string="Payment to Other Party")
    line_ids = fields.One2many(
        "pc.payment.request.line",
        "request_id",
        string="Payment Lines",
        copy=True,
    )
    amount_total = fields.Monetary(
        compute="_compute_amounts",
        store=True,
        tracking=True,
    )
    amount_currency = fields.Monetary(
        string="Base Currency Amount",
        currency_field="company_currency_id",
        compute="_compute_amounts",
        store=True,
        help="Request total converted to the company's currency for approval matching.",
    )
    matrix_id = fields.Many2one(
        "pc.approval.matrix",
        string="Applied Approval Matrix",
        readonly=True,
        copy=False,
        check_company=True,
        tracking=True,
    )
    approval_ids = fields.One2many(
        "pc.payment.request.approval",
        "request_id",
        string="Approvals",
        copy=False,
    )
    current_approval_sequence = fields.Integer(
        compute="_compute_approval_status",
        string="Current Approval Level",
    )
    can_current_user_approve = fields.Boolean(compute="_compute_approval_status")
    approval_progress = fields.Char(compute="_compute_approval_status")
    submitted_by_id = fields.Many2one("res.users", readonly=True, copy=False)
    approved_by_id = fields.Many2one("res.users", readonly=True, copy=False)
    rejected_by_id = fields.Many2one("res.users", readonly=True, copy=False)
    date_submitted = fields.Datetime(readonly=True, copy=False)
    date_approved = fields.Datetime(readonly=True, copy=False)
    date_rejected = fields.Datetime(readonly=True, copy=False)
    reject_reason = fields.Text(readonly=True, copy=False)
    payment_id = fields.Many2one(
        "account.payment",
        string="Related Payment",
        check_company=True,
        copy=False,
        tracking=True,
    )
    is_locked = fields.Boolean(compute="_compute_is_locked")

    @api.model
    def _default_department(self, user=None, company=None):
        user = user or self.env.user
        company = company or self.env.company
        employee = self.env["hr.employee"].sudo().search(
            [("user_id", "=", user.id), ("company_id", "=", company.id)],
            limit=1,
        )
        return employee.department_id

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not self.env.context.get("payment_request_migration"):
                vals["state"] = "draft"
            company = self.env["res.company"].browse(
                vals.get("company_id") or self.env.company.id
            )
            if not vals.get("currency_id"):
                vals["currency_id"] = company.currency_id.id
            if not vals.get("department_id"):
                requester = self.env["res.users"].browse(
                    vals.get("requester_id") or self.env.user.id
                )
                department = self._default_department(requester, company)
                if department:
                    vals["department_id"] = department.id
            if vals.get("name", _("New")) == _("New"):
                vals["name"] = (
                    self.env["ir.sequence"]
                    .with_company(company)
                    .next_by_code("pc.payment.request")
                    or _("New")
                )
        return super().create(vals_list)

    @api.onchange("company_id")
    def _onchange_company_id(self):
        if self.company_id:
            self.currency_id = self.company_id.currency_id
            department = self._default_department(self.requester_id, self.company_id)
            if department:
                self.department_id = department

    @api.onchange("requester_id")
    def _onchange_requester_id(self):
        department = self._default_department(self.requester_id, self.company_id)
        if department:
            self.department_id = department

    @api.depends(
        "line_ids.amount",
        "currency_id",
        "company_id",
        "required_date",
    )
    def _compute_amounts(self):
        for request in self:
            total = sum(request.line_ids.mapped("amount"))
            request.amount_total = total
            if request.currency_id and request.company_id:
                conversion_date = request.required_date or fields.Date.context_today(request)
                request.amount_currency = request.currency_id._convert(
                    total,
                    request.company_id.currency_id,
                    request.company_id,
                    conversion_date,
                )
            else:
                request.amount_currency = total

    @api.depends("state")
    def _compute_is_locked(self):
        for request in self:
            request.is_locked = request.state not in ("draft", "rejected")

    @api.depends(
        "state",
        "approval_ids.state",
        "approval_ids.sequence",
        "approval_ids.user_id",
    )
    @api.depends_context("uid")
    def _compute_approval_status(self):
        current_user = self.env.user
        for request in self:
            pending = request.approval_ids.filtered(lambda approval: approval.state == "pending")
            current_sequence = min(pending.mapped("sequence"), default=0)
            current_lines = pending.filtered(
                lambda approval: approval.sequence == current_sequence
            )
            approved_count = len(
                request.approval_ids.filtered(lambda approval: approval.state == "approved")
            )
            total_count = len(
                request.approval_ids.filtered(
                    lambda approval: approval.state not in ("skipped", "cancelled")
                )
            )
            request.current_approval_sequence = current_sequence
            request.can_current_user_approve = bool(
                request.state == "waiting_approval"
                and current_lines.filtered(lambda approval: approval.user_id == current_user)
            )
            request.approval_progress = _("%(approved)s of %(total)s approved") % {
                "approved": approved_count,
                "total": total_count,
            }

    @api.constrains("line_ids", "amount_total")
    def _check_positive_total(self):
        for request in self:
            if request.line_ids and request.amount_total <= 0:
                raise ValidationError(_("The payment request total must be positive."))

    def write(self, vals):
        if "state" in vals and not self.env.context.get("skip_payment_request_lock"):
            raise AccessError(_("Use the payment request workflow buttons to change status."))
        protected_fields = {
            "company_id",
            "currency_id",
            "requester_id",
            "department_id",
            "partner_id",
            "journal_id",
            "payment_method",
            "required_date",
            "payment_details",
            "is_payment_other",
            "line_ids",
        }
        if (
            not self.env.context.get("skip_payment_request_lock")
            and protected_fields.intersection(vals)
        ):
            locked = self.filtered(lambda request: request.state not in ("draft", "rejected"))
            if locked:
                raise UserError(_("Only draft or rejected requests can be edited."))
        return super().write(vals)

    def unlink(self):
        if any(request.state not in ("draft", "rejected", "cancelled") for request in self):
            raise UserError(_("Only draft, rejected, or cancelled requests can be deleted."))
        if not self.env.user.has_group("pc_payment_request_v19.group_payment_request_manager"):
            if any(request.requester_id != self.env.user for request in self):
                raise AccessError(_("You can only delete your own payment requests."))
        return super().unlink()

    def _validate_before_submit(self):
        self.ensure_one()
        if self.state not in ("draft", "rejected"):
            raise UserError(_("Only draft or rejected requests can be submitted."))
        if not self.line_ids:
            raise UserError(_("Add at least one payment line before submitting."))
        if any(line.amount <= 0 for line in self.line_ids):
            raise UserError(_("Every payment line must have a positive amount."))

    def action_submit(self):
        for request in self:
            request._validate_before_submit()
            matrix = self.env["pc.approval.matrix"].find_matrix(
                request.department_id,
                request.amount_currency,
                request.company_id,
            )
            if not matrix:
                raise UserError(
                    _(
                        "No active approval matrix matches department %(department)s "
                        "and base amount %(amount).2f."
                    )
                    % {
                        "department": request.department_id.display_name,
                        "amount": request.amount_currency,
                    }
                )
            if not matrix.stage_ids:
                raise UserError(_("The selected approval matrix has no approval stages."))

            approval_values = []
            for stage in matrix.stage_ids.sorted("sequence"):
                approvers = stage.effective_approvers(request.department_id)
                if not approvers:
                    raise UserError(
                        _("Approval stage '%s' has no active approvers.") % stage.display_name
                    )
                if not stage.require_all_approvers and stage.minimum_approvals > len(approvers):
                    raise UserError(
                        _("Approval stage '%s' requires more approvals than available users.")
                        % stage.display_name
                    )
                for approver in approvers:
                    approval_values.append(
                        {
                            "request_id": request.id,
                            "stage_id": stage.id,
                            "stage_name": stage.name,
                            "sequence": stage.sequence,
                            "user_id": approver.id,
                            "require_all_approvers": stage.require_all_approvers,
                            "minimum_approvals": stage.minimum_approvals,
                        }
                    )

            request.approval_ids.sudo().unlink()
            self.env["pc.payment.request.approval"].sudo().create(approval_values)
            request.with_context(skip_payment_request_lock=True).write(
                {
                    "state": "waiting_approval",
                    "matrix_id": matrix.id,
                    "submitted_by_id": self.env.user.id,
                    "date_submitted": fields.Datetime.now(),
                    "approved_by_id": False,
                    "date_approved": False,
                    "rejected_by_id": False,
                    "date_rejected": False,
                    "reject_reason": False,
                }
            )
            request.message_post(body=_("Payment request submitted for approval."))
            request._schedule_current_approval_activities()
        return True

    def _current_pending_lines(self):
        self.ensure_one()
        pending = self.approval_ids.filtered(lambda approval: approval.state == "pending")
        if not pending:
            return pending
        current_sequence = min(pending.mapped("sequence"))
        return pending.filtered(lambda approval: approval.sequence == current_sequence)

    def _schedule_current_approval_activities(self):
        todo_type = self.env.ref("mail.mail_activity_data_todo", raise_if_not_found=False)
        if not todo_type:
            return
        for request in self:
            current_lines = request._current_pending_lines()
            for user in current_lines.mapped("user_id"):
                existing = request.activity_ids.filtered(
                    lambda activity: activity.user_id == user
                    and activity.activity_type_id == todo_type
                )
                if not existing:
                    request.activity_schedule(
                        "mail.mail_activity_data_todo",
                        user_id=user.id,
                        summary=_("Approve payment request %s") % request.name,
                    )

    def _clear_approval_activities(self, users=None):
        todo_type = self.env.ref("mail.mail_activity_data_todo", raise_if_not_found=False)
        for request in self:
            activities = request.activity_ids
            if todo_type:
                activities = activities.filtered(
                    lambda activity: activity.activity_type_id == todo_type
                )
            if users:
                activities = activities.filtered(lambda activity: activity.user_id in users)
            activities.sudo().unlink()

    def action_approve(self):
        for request in self:
            if request.state != "waiting_approval":
                raise UserError(_("This request is not waiting for approval."))
            current_lines = request._current_pending_lines()
            user_line = current_lines.filtered(
                lambda approval: approval.user_id == self.env.user
            )[:1]
            if not user_line:
                raise AccessError(_("You are not a current approver for this request."))

            user_line.sudo().write(
                {"state": "approved", "decision_date": fields.Datetime.now()}
            )
            request._clear_approval_activities(self.env.user)

            stage_lines = request.approval_ids.filtered(
                lambda approval: approval.sequence == user_line.sequence
            )
            if user_line.require_all_approvers:
                stage_complete = all(line.state == "approved" for line in stage_lines)
            else:
                approved_count = len(
                    stage_lines.filtered(lambda approval: approval.state == "approved")
                )
                stage_complete = approved_count >= user_line.minimum_approvals

            if not stage_complete:
                request.message_post(
                    body=_("Approved by %s; more approvals are required at this level.")
                    % self.env.user.display_name
                )
                continue

            if not user_line.require_all_approvers:
                stage_lines.filtered(
                    lambda approval: approval.state == "pending"
                ).sudo().write({"state": "skipped"})
                request._clear_approval_activities(stage_lines.mapped("user_id"))

            if request.approval_ids.filtered(lambda approval: approval.state == "pending"):
                request.message_post(
                    body=_("Approval level %(level)s completed by %(user)s.")
                    % {
                        "level": user_line.sequence,
                        "user": self.env.user.display_name,
                    }
                )
                request._schedule_current_approval_activities()
            else:
                request.with_context(skip_payment_request_lock=True).write(
                    {
                        "state": "approved",
                        "approved_by_id": self.env.user.id,
                        "date_approved": fields.Datetime.now(),
                    }
                )
                request._clear_approval_activities()
                request.message_post(body=_("Payment request fully approved."))
        return True

    def action_open_reject_wizard(self):
        self.ensure_one()
        if self.state != "waiting_approval" or not self.can_current_user_approve:
            raise AccessError(_("You are not a current approver for this request."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Reject Payment Request"),
            "res_model": "pc.payment.request.reject.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_request_id": self.id},
        }

    def _action_reject(self, reason):
        self.ensure_one()
        if self.state != "waiting_approval":
            raise UserError(_("This request is not waiting for approval."))
        current_lines = self._current_pending_lines()
        user_line = current_lines.filtered(
            lambda approval: approval.user_id == self.env.user
        )[:1]
        if not user_line:
            raise AccessError(_("You are not a current approver for this request."))
        user_line.sudo().write(
            {
                "state": "rejected",
                "decision_date": fields.Datetime.now(),
                "comment": reason,
            }
        )
        self.approval_ids.filtered(
            lambda approval: approval.state == "pending"
        ).sudo().write({"state": "cancelled"})
        self.with_context(skip_payment_request_lock=True).write(
            {
                "state": "rejected",
                "rejected_by_id": self.env.user.id,
                "date_rejected": fields.Datetime.now(),
                "reject_reason": reason,
            }
        )
        self._clear_approval_activities()
        self.message_post(
            body=_("Payment request rejected by %(user)s. Reason: %(reason)s")
            % {"user": self.env.user.display_name, "reason": reason}
        )
        return True

    def action_reset_to_draft(self):
        for request in self:
            if request.state not in ("rejected", "cancelled"):
                raise UserError(_("Only rejected or cancelled requests can be reset."))
            if (
                request.requester_id != self.env.user
                and not self.env.user.has_group(
                    "pc_payment_request_v19.group_payment_request_manager"
                )
            ):
                raise AccessError(_("Only the requester or a manager can reset this request."))
            request._clear_approval_activities()
            request.approval_ids.sudo().unlink()
            request.with_context(skip_payment_request_lock=True).write(
                {
                    "state": "draft",
                    "matrix_id": False,
                    "submitted_by_id": False,
                    "date_submitted": False,
                    "approved_by_id": False,
                    "date_approved": False,
                    "rejected_by_id": False,
                    "date_rejected": False,
                    "reject_reason": False,
                }
            )
        return True

    def action_cancel(self):
        for request in self:
            if request.state not in ("draft", "waiting_approval", "rejected"):
                raise UserError(_("This request can no longer be cancelled."))
            request.approval_ids.filtered(
                lambda approval: approval.state == "pending"
            ).sudo().write({"state": "cancelled"})
            request._clear_approval_activities()
            request.with_context(skip_payment_request_lock=True).write(
                {"state": "cancelled"}
            )
        return True

    def action_mark_paid(self):
        if not self.env.user.has_group(
            "pc_payment_request_v19.group_payment_request_manager"
        ):
            raise AccessError(_("Only Payment Request Managers can mark requests as paid."))
        for request in self:
            if request.state != "approved":
                raise UserError(_("Only approved requests can be marked as paid."))
            request.with_context(skip_payment_request_lock=True).write({"state": "paid"})
            request.message_post(body=_("Payment request marked as paid."))
        return True

    def action_open_payment(self):
        self.ensure_one()
        if not self.payment_id:
            return False
        return {
            "type": "ir.actions.act_window",
            "name": _("Payment"),
            "res_model": "account.payment",
            "res_id": self.payment_id.id,
            "view_mode": "form",
        }


class PcPaymentRequestLine(models.Model):
    _name = "pc.payment.request.line"
    _description = "Payment Request Line"
    _order = "sequence, id"
    _check_company_auto = True

    sequence = fields.Integer(default=10)
    request_id = fields.Many2one(
        "pc.payment.request",
        required=True,
        ondelete="cascade",
        index=True,
    )
    company_id = fields.Many2one(
        related="request_id.company_id",
        store=True,
        readonly=True,
    )
    currency_id = fields.Many2one(
        related="request_id.currency_id",
        store=True,
        readonly=True,
    )
    name = fields.Char(string="Description", required=True)
    partner_id = fields.Many2one(
        "res.partner",
        string="Vendor / Payee",
        check_company=True,
    )
    partner_bank_id = fields.Many2one(
        "res.partner.bank",
        string="Vendor Bank Account",
        check_company=True,
    )
    account_id = fields.Many2one(
        "account.account",
        string="Account",
        check_company=True,
    )
    analytic_account_id = fields.Many2one(
        "account.analytic.account",
        string="Analytic Account",
        check_company=True,
    )
    amount = fields.Monetary(required=True)

    @api.onchange("request_id")
    def _onchange_request_id(self):
        if self.request_id and not self.partner_id:
            self.partner_id = self.request_id.partner_id

    def _ensure_request_editable(self, requests=None):
        requests = requests or self.mapped("request_id")
        if any(request.state not in ("draft", "rejected") for request in requests):
            raise UserError(_("Payment lines can only be changed on draft or rejected requests."))

    @api.model_create_multi
    def create(self, vals_list):
        requests = self.env["pc.payment.request"].browse(
            [vals.get("request_id") for vals in vals_list if vals.get("request_id")]
        )
        self._ensure_request_editable(requests)
        return super().create(vals_list)

    def write(self, vals):
        self._ensure_request_editable()
        if vals.get("request_id"):
            self._ensure_request_editable(
                self.env["pc.payment.request"].browse(vals["request_id"])
            )
        return super().write(vals)

    def unlink(self):
        self._ensure_request_editable()
        return super().unlink()

    @api.constrains("amount")
    def _check_amount(self):
        for line in self:
            if line.amount <= 0:
                raise ValidationError(_("Payment line amounts must be positive."))


class PcPaymentRequestApproval(models.Model):
    _name = "pc.payment.request.approval"
    _description = "Payment Request Approval"
    _order = "sequence, id"

    request_id = fields.Many2one(
        "pc.payment.request",
        required=True,
        ondelete="cascade",
        index=True,
    )
    company_id = fields.Many2one(
        related="request_id.company_id",
        store=True,
        readonly=True,
    )
    stage_id = fields.Many2one(
        "pc.approval.matrix.stage",
        required=True,
        ondelete="restrict",
    )
    stage_name = fields.Char(required=True, readonly=True)
    sequence = fields.Integer(required=True, readonly=True)
    user_id = fields.Many2one("res.users", required=True, readonly=True, index=True)
    require_all_approvers = fields.Boolean(default=True, readonly=True)
    minimum_approvals = fields.Integer(default=1, readonly=True)
    state = fields.Selection(
        [
            ("pending", "Pending"),
            ("approved", "Approved"),
            ("rejected", "Rejected"),
            ("skipped", "Skipped"),
            ("cancelled", "Cancelled"),
        ],
        default="pending",
        required=True,
        readonly=True,
        index=True,
    )
    decision_date = fields.Datetime(readonly=True)
    comment = fields.Text(readonly=True)

    _unique_request_user_sequence = models.Constraint(
        "UNIQUE(request_id, user_id, sequence)",
        "An approver can only occur once at each request approval level.",
    )
