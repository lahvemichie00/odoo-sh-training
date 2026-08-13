from ast import literal_eval

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError


class ApprovalMatrix(models.Model):
    _name = "approval.matrix"
    _description = "Approval Matrix"
    _order = "id"

    name = fields.Char(required=True, index=True)
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company, index=True
    )
    model_id = fields.Many2one(
        "ir.model",
        string="Model",
        required=True,
        ondelete="cascade",
        domain="[('transient', '=', False)]",
    )
    res_model = fields.Char(
        string="Res Model", related="model_id.model", store=True, readonly=True, index=True
    )
    active = fields.Boolean(default=True)
    dept_manager_as_approver = fields.Boolean(string="Dept. Manager as Approver")
    user_request_field_id = fields.Many2one(
        "ir.model.fields",
        string="User Requester Field",
        domain="[('model_id', '=', model_id), ('ttype', '=', 'many2one'), ('relation', '=', 'res.users')]",
        ondelete="set null",
    )
    rule_ids = fields.One2many(
        "approval.matrix.rule", "matrix_id", string="Rules", copy=True
    )
    approver_ids = fields.One2many(
        "approval.matrix.approver", "matrix_id", string="Approvers", copy=True
    )
    approver_summary = fields.Char(compute="_compute_approver_summary")

    @api.depends("approver_ids.user_ids", "approver_ids.seq")
    def _compute_approver_summary(self):
        for matrix in self:
            names = matrix.approver_ids.sorted("seq").mapped("user_ids.name")
            matrix.approver_summary = ", ".join(names)

    @api.constrains("user_request_field_id", "model_id")
    def _check_requester_field(self):
        for matrix in self:
            if (
                matrix.user_request_field_id
                and matrix.user_request_field_id.model_id != matrix.model_id
            ):
                raise ValidationError(_("The requester field must belong to the selected model."))

    @api.model
    def find_for_record(self, record):
        """Return the first active matrix whose complete rule set matches record."""
        record.ensure_one()
        company = record.company_id if "company_id" in record._fields else self.env.company
        matrices = self.sudo().search(
            [
                ("active", "=", True),
                ("company_id", "=", company.id),
                ("res_model", "=", record._name),
            ],
            order="id",
        )
        return matrices.filtered(lambda matrix: matrix._matches_record(record))[:1]

    def _matches_record(self, record):
        self.ensure_one()
        return all(rule._matches_record(record) for rule in self.rule_ids)

    def _requester_user(self, record):
        self.ensure_one()
        if self.user_request_field_id:
            return record[self.user_request_field_id.name]
        for field_name in ("user_request_id", "user_id", "requester_id"):
            if field_name in record._fields and record[field_name]:
                return record[field_name]
        return self.env["res.users"]

    def _department_manager_user(self, record):
        self.ensure_one()
        department = (
            record.department_id
            if "department_id" in record._fields and record.department_id
            else self.env["hr.department"]
        )
        if not department:
            requester = self._requester_user(record)
            employee = self.env["hr.employee"].sudo().search(
                [
                    ("user_id", "=", requester.id),
                    ("company_id", "=", self.company_id.id),
                ],
                limit=1,
            )
            department = employee.department_id
        return department.manager_id.user_id if department.manager_id else self.env["res.users"]

    def create_document_approvals(self, record, replace=True):
        self.ensure_one()
        record.ensure_one()
        Approval = self.env["approval.matrix.document.approval"].sudo()
        domain = [("res_model", "=", record._name), ("res_id", "=", record.id)]
        existing = Approval.search(domain)
        if existing and not replace:
            return existing
        existing.unlink()

        stages = self.approver_ids.sorted(lambda stage: (stage.seq, stage.id))
        manager_user = (
            self._department_manager_user(record)
            if self.dept_manager_as_approver
            else self.env["res.users"]
        )
        if not stages and not manager_user:
            raise UserError(_("The selected approval matrix has no approvers."))

        values = []
        if not stages and manager_user:
            values.append(
                self._document_approval_values(record, 0, manager_user, True, 1)
            )
        for index, stage in enumerate(stages):
            users = stage.user_ids.filtered(lambda user: user.active and not user.share)
            if manager_user and index == 0:
                users |= manager_user
            if not users:
                raise UserError(
                    _("Approval level %s has no active internal approvers.") % stage.seq
                )
            minimum = len(users) if stage.require_all_approver else stage.min_approver
            if minimum < 1 or minimum > len(users):
                raise UserError(
                    _("Approval level %s has an invalid minimum approver count.")
                    % stage.seq
                )
            values.append(
                self._document_approval_values(
                    record, stage.seq, users, stage.require_all_approver, minimum
                )
            )
        return Approval.create(values)

    def _document_approval_values(
        self, record, sequence, users, require_all, minimum
    ):
        return {
            "res_model_id": self.model_id.id,
            "res_model": record._name,
            "res_id": record.id,
            "res_name": record.display_name,
            "matrix_id": self.id,
            "approver_seq": sequence,
            "approver_ids": [(6, 0, users.ids)],
            "require_all_approver": require_all,
            "minimum_approved": minimum,
        }


class ApprovalMatrixRule(models.Model):
    _name = "approval.matrix.rule"
    _description = "Approval Matrix Rule"
    _order = "id"

    matrix_id = fields.Many2one(
        "approval.matrix", required=True, ondelete="cascade", index=True
    )
    company_id = fields.Many2one(related="matrix_id.company_id", store=True)
    model_id = fields.Many2one(related="matrix_id.model_id", string="Model", store=True)
    field_id = fields.Many2one(
        "ir.model.fields",
        string="Field",
        required=True,
        ondelete="cascade",
        domain="[('model_id', '=', model_id), ('store', '=', True)]",
    )
    operator = fields.Selection(
        [
            ("=", "="),
            ("!=", "!="),
            (">", ">"),
            (">=", ">="),
            ("<", "<"),
            ("<=", "<="),
            ("in", "in"),
            ("not in", "not in"),
        ],
        required=True,
        default="=",
    )
    value = fields.Char(required=True)
    related_field_model = fields.Char(
        related="field_id.relation", store=True, readonly=True
    )
    m2o_value_id = fields.Integer(string="Relation Val", default=0)

    @api.onchange("field_id")
    def _onchange_field_id(self):
        if self.field_id.ttype != "many2one":
            self.m2o_value_id = 0

    @api.constrains("field_id", "matrix_id")
    def _check_field_model(self):
        for rule in self:
            if rule.field_id.model_id != rule.matrix_id.model_id:
                raise ValidationError(_("Every rule field must belong to the matrix model."))

    def _coerce_expected(self):
        self.ensure_one()
        field_type = self.field_id.ttype
        raw = self.value
        if field_type == "many2one":
            return self.m2o_value_id or int(raw or 0)
        if field_type in ("integer",):
            return int(raw or 0)
        if field_type in ("float", "monetary"):
            return float(raw or 0.0)
        if field_type == "boolean":
            return str(raw).strip().lower() in ("1", "true", "t", "yes")
        if self.operator in ("in", "not in"):
            try:
                value = literal_eval(raw)
                return value if isinstance(value, (list, tuple, set)) else [value]
            except (SyntaxError, ValueError):
                return [item.strip() for item in raw.split(",")]
        return raw

    def _matches_record(self, record):
        self.ensure_one()

        field_name = self.field_id.name

        # Direct field
        if field_name in record._fields:
            actual = record[field_name]

        # Related field support e.g. line_ids.qty
        elif "." in field_name:
            parts = field_name.split(".")
            actual = record

            for part in parts:
                if not actual:
                    return False

                if isinstance(actual, models.BaseModel):
                    actual = actual.mapped(part)

        else:
            return False


        if isinstance(actual, models.BaseModel):
            actual = actual.ids


        if self.field_id.ttype == "many2one":
            actual = actual.id if actual else False

        elif self.field_id.ttype in ("one2many", "many2many"):
            actual = actual.ids


        expected = self._coerce_expected()


        operations = {
            "=": lambda left, right: left == right,
            "!=": lambda left, right: left != right,
            ">": lambda left, right: left > right,
            ">=": lambda left, right: left >= right,
            "<": lambda left, right: left < right,
            "<=": lambda left, right: left <= right,
            "in": lambda left, right: left in right,
            "not in": lambda left, right: left not in right,
        }


        try:
            if isinstance(actual, list):
                return any(
                    operations[self.operator](value, expected)
                    for value in actual
                )

            return operations[self.operator](actual, expected)

        except (TypeError, ValueError):
            return False


class ApprovalMatrixApprover(models.Model):
    _name = "approval.matrix.approver"
    _description = "Approval Matrix Approver"
    _order = "seq, id"

    seq = fields.Integer(string="Seq", required=True, default=0)
    matrix_id = fields.Many2one(
        "approval.matrix", required=True, ondelete="cascade", index=True
    )
    user_ids = fields.Many2many(
        "res.users",
        "approval_matrix_rule_approver_res_users_rel",
        "approval_matrix_rule_approver_id",
        "res_users_id",
        string="Users",
        domain=[("share", "=", False)],
    )
    require_all_approver = fields.Boolean(string="Required All Approver", default=True)
    min_approver = fields.Integer(string="Min Approver", required=True, default=1)

    @api.constrains("min_approver", "user_ids", "require_all_approver")
    def _check_minimum(self):
        for stage in self:
            if stage.min_approver < 1:
                raise ValidationError(_("Minimum approvers must be at least one."))
            if (
                not stage.require_all_approver
                and stage.user_ids
                and stage.min_approver > len(stage.user_ids)
            ):
                raise ValidationError(
                    _("Minimum approvers cannot exceed the configured users.")
                )


class ApprovalMatrixDocumentApproval(models.Model):
    _name = "approval.matrix.document.approval"
    _description = "Document Approval"
    _order = "res_model, res_id, approver_seq, id"
    _rec_name = "res_name"

    res_model_id = fields.Many2one(
        "ir.model", string="Related Document Model", required=True, ondelete="cascade"
    )
    res_model = fields.Char(required=True, index=True)
    res_id = fields.Integer(required=True, index=True)
    res_name = fields.Char(string="Document Name", required=True)
    matrix_id = fields.Many2one(
        "approval.matrix", string="Matrix", required=True, ondelete="cascade", index=True
    )
    approver_seq = fields.Integer(string="Approver Level", required=True, default=0)
    approver_ids = fields.Many2many(
        "res.users",
        "approval_matrix_doc_approval_user_rel",
        "approval_id",
        "user_id",
        string="Approvers",
    )
    require_all_approver = fields.Boolean(default=True)
    minimum_approved = fields.Integer(string="Min. Approved", required=True, default=1)
    approved_by_ids = fields.Many2many(
        "res.users",
        "approval_matrix_doc_approved_by_rel",
        "approval_id",
        "user_id",
        string="Approved By",
    )
    rejected_by_ids = fields.Many2many(
        "res.users",
        "approval_matrix_doc_rejected_by_rel",
        "approval_id",
        "user_id",
        string="Rejected By",
    )
    approved_count = fields.Integer(compute="_compute_counts", store=True)
    rejected_count = fields.Integer(compute="_compute_counts", store=True)
    is_approved = fields.Boolean(string="Is Approved", compute="_compute_counts", store=True)
    active = fields.Boolean(default=True)
    can_current_user_approve = fields.Boolean(compute="_compute_can_current_user_approve")

    @api.depends(
        "approved_by_ids", "rejected_by_ids", "minimum_approved", "require_all_approver", "approver_ids"
    )
    def _compute_counts(self):
        for approval in self:
            approval.approved_count = len(approval.approved_by_ids)
            approval.rejected_count = len(approval.rejected_by_ids)
            required = (
                len(approval.approver_ids)
                if approval.require_all_approver
                else approval.minimum_approved
            )
            approval.is_approved = bool(required and approval.approved_count >= required)

    @api.depends("approver_ids", "approved_by_ids", "rejected_by_ids", "active")
    @api.depends_context("uid")
    def _compute_can_current_user_approve(self):
        user = self.env.user
        for approval in self:
            approval.can_current_user_approve = bool(
                approval.active
                and user in approval.approver_ids
                and user not in approval.approved_by_ids
                and user not in approval.rejected_by_ids
                and not approval.is_approved
            )

    def _document(self):
        self.ensure_one()
        if self.res_model not in self.env:
            return self.env["approval.matrix.document.approval"]
        return self.env[self.res_model].browse(self.res_id).exists()

    def action_send_notification(self):
        for approval in self:
            document = approval._document()
            if not document or not hasattr(document, "activity_schedule"):
                continue
            for user in (approval.approver_ids - approval.approved_by_ids - approval.rejected_by_ids):
                document.activity_schedule(
                    "mail.mail_activity_data_todo",
                    user_id=user.id,
                    summary=_("Approval required: %s") % approval.res_name,
                )
        return True

    def action_open_document(self):
        self.ensure_one()
        document = self._document()
        if not document:
            raise UserError(_("The related document no longer exists."))
        return {
            "type": "ir.actions.act_window",
            "res_model": self.res_model,
            "res_id": self.res_id,
            "view_mode": "form",
            "target": "current",
        }


class RejectionMessage(models.Model):
    _name = "rejection.message"
    _description = "Rejection Message"
    _order = "name, id"

    res_model_id = fields.Many2one(
        "ir.model", string="Document Model", ondelete="cascade"
    )
    res_model = fields.Char(
        string="Related Document Model", related="res_model_id.model", store=True
    )
    name = fields.Char(string="Reason", required=True)
    active = fields.Boolean(default=True)


class ApprovalMatrixMixin(models.AbstractModel):
    _name = "approval.matrix.mixin"
    _description = "Approval Matrix Document Mixin"

    approval_matrix_id = fields.Many2one(
        "approval.matrix", string="Matrix", readonly=True, copy=False
    )
    approval_document_ids = fields.Many2many(
        "approval.matrix.document.approval",
        string="Approvals",
        compute="_compute_approval_matrix_status",
    )
    approval_can_current_user = fields.Boolean(compute="_compute_approval_matrix_status")
    approval_is_approved = fields.Boolean(compute="_compute_approval_matrix_status")
    approval_current_level = fields.Integer(compute="_compute_approval_matrix_status")

    @api.depends("approval_matrix_id")
    @api.depends_context("uid")
    def _compute_approval_matrix_status(self):
        Approval = self.env["approval.matrix.document.approval"]
        user = self.env.user
        for document in self:
            approvals = Approval.search(
                [("res_model", "=", document._name), ("res_id", "=", document.id)],
                order="approver_seq,id",
            ) if document.id else Approval
            document.approval_document_ids = approvals
            pending = approvals.filtered(
                lambda approval: approval.active
                and not approval.is_approved
                and not approval.rejected_by_ids
            )
            current_level = min(pending.mapped("approver_seq"), default=0)
            current = pending.filtered(lambda approval: approval.approver_seq == current_level)
            document.approval_current_level = current_level
            document.approval_can_current_user = bool(
                current.filtered(
                    lambda approval: user in approval.approver_ids
                    and user not in approval.approved_by_ids
                    and user not in approval.rejected_by_ids
                )
            )
            document.approval_is_approved = bool(approvals and all(approvals.mapped("is_approved")))

    def _approval_refresh(self, replace=True):
        for document in self:
            matrix = self.env["approval.matrix"].find_for_record(document)
            if not matrix:
                raise UserError(
                    _("No active approval matrix matches %s.") % document.display_name
                )
            matrix.create_document_approvals(document, replace=replace)
            document.approval_matrix_id = matrix
        return True

    def action_fetch_matrix(self):
        for document in self:
            terminal = "state" in document._fields and document.state in (
                "approved", "paid", "reject", "rejected"
            )
            document._approval_refresh(replace=not terminal)
        return True

    def _approval_current_records(self):
        self.ensure_one()
        approvals = self.env["approval.matrix.document.approval"].search(
            [
                ("res_model", "=", self._name),
                ("res_id", "=", self.id),
                ("active", "=", True),
                ("is_approved", "=", False),
                ("rejected_by_ids", "=", False),
            ],
            order="approver_seq,id",
        )
        if not approvals:
            return approvals
        level = min(approvals.mapped("approver_seq"))
        return approvals.filtered(lambda approval: approval.approver_seq == level)

    def _approval_action_approve(self):
        for document in self:
            current = document._approval_current_records()
            approval = current.filtered(
                lambda item: self.env.user in item.approver_ids
                and self.env.user not in item.approved_by_ids
            )[:1]
            if not approval:
                raise AccessError(_("You are not a current approver for this document."))
            approval.sudo().write({"approved_by_ids": [(4, self.env.user.id)]})
            document._approval_level_approved(self.env.user, approval)
            document.invalidate_recordset(
                ["approval_document_ids", "approval_can_current_user", "approval_is_approved", "approval_current_level"]
            )
            remaining = document._approval_current_records()
            if not remaining:
                document._approval_matrix_approved(self.env.user)
        return True

    def action_open_approval_reject_wizard(self):
        self.ensure_one()
        if not self.approval_can_current_user:
            raise AccessError(_("You are not a current approver for this document."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Reject Document"),
            "res_model": "approval.matrix.reject.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_res_model": self._name,
                "default_res_id": self.id,
            },
        }

    def _approval_action_reject(self, reason):
        self.ensure_one()
        current = self._approval_current_records()
        approval = current.filtered(lambda item: self.env.user in item.approver_ids)[:1]
        if not approval:
            raise AccessError(_("You are not a current approver for this document."))
        approval.sudo().write({"rejected_by_ids": [(4, self.env.user.id)]})
        self._approval_matrix_rejected(self.env.user, reason)
        self.invalidate_recordset(
            ["approval_document_ids", "approval_can_current_user", "approval_is_approved", "approval_current_level"]
        )
        return True

    def _approval_level_approved(self, user, approval):
        return True

    def _approval_matrix_approved(self, user):
        raise NotImplementedError()

    def _approval_matrix_rejected(self, user, reason):
        raise NotImplementedError()
