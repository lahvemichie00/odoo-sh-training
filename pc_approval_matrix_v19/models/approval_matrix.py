from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class PcApprovalMatrix(models.Model):
    _name = "pc.approval.matrix"
    _description = "Approval Matrix"
    _order = "sequence, id"

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
    sequence = fields.Integer(default=10)
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    currency_id = fields.Many2one(
        related="company_id.currency_id",
        store=True,
        readonly=True,
    )
    department_id = fields.Many2one(
        "hr.department",
        string="Department",
        check_company=True,
        index=True,
        help="Leave empty to use this matrix as a fallback for all departments.",
    )
    minimum_amount = fields.Monetary(default=0.0, required=True)
    minimum_inclusive = fields.Boolean(
        default=True,
        help="If enabled, the minimum amount is included in the range.",
    )
    has_maximum = fields.Boolean(string="Use Maximum Amount", default=True)
    maximum_amount = fields.Monetary(default=2000.0)
    maximum_inclusive = fields.Boolean(
        default=True,
        help="If enabled, the maximum amount is included in the range.",
    )
    stage_ids = fields.One2many(
        "pc.approval.matrix.stage",
        "matrix_id",
        string="Approval Stages",
        copy=True,
    )

    @api.constrains(
        "minimum_amount",
        "maximum_amount",
        "has_maximum",
        "minimum_inclusive",
        "maximum_inclusive",
    )
    def _check_amount_range(self):
        for matrix in self:
            if matrix.minimum_amount < 0:
                raise ValidationError(_("The minimum amount cannot be negative."))
            if matrix.has_maximum:
                if matrix.maximum_amount < matrix.minimum_amount:
                    raise ValidationError(
                        _("The maximum amount cannot be lower than the minimum amount.")
                    )
                if (
                    matrix.maximum_amount == matrix.minimum_amount
                    and not matrix.minimum_inclusive
                    and not matrix.maximum_inclusive
                ):
                    raise ValidationError(_("The configured amount range is empty."))

    def _matches_amount(self, amount):
        self.ensure_one()
        lower_match = (
            amount >= self.minimum_amount
            if self.minimum_inclusive
            else amount > self.minimum_amount
        )
        if not lower_match:
            return False
        if not self.has_maximum:
            return True
        return (
            amount <= self.maximum_amount
            if self.maximum_inclusive
            else amount < self.maximum_amount
        )

    @api.model
    def find_matrix(self, department, amount, company=None):
        """Return the best active matrix for a company, department and base amount."""
        company = company or self.env.company
        department_id = department.id if department else False
        candidates = self.sudo().search(
            [
                ("active", "=", True),
                ("company_id", "=", company.id),
                ("department_id", "in", [department_id, False]),
            ]
        )
        matches = candidates.filtered(lambda matrix: matrix._matches_amount(amount))
        exact_matches = matches.filtered(
            lambda matrix: matrix.department_id.id == department_id
        )
        return exact_matches[:1] or matches.filtered(lambda matrix: not matrix.department_id)[:1]


class PcApprovalMatrixStage(models.Model):
    _name = "pc.approval.matrix.stage"
    _description = "Approval Matrix Stage"
    _order = "sequence, id"

    name = fields.Char(required=True, default=lambda self: _("Approval"))
    matrix_id = fields.Many2one(
        "pc.approval.matrix",
        required=True,
        ondelete="cascade",
        index=True,
    )
    company_id = fields.Many2one(
        related="matrix_id.company_id",
        store=True,
        readonly=True,
    )
    sequence = fields.Integer(required=True, default=0)
    approver_ids = fields.Many2many(
        "res.users",
        "pc_approval_stage_user_rel",
        "stage_id",
        "user_id",
        string="Approvers",
        domain=[("share", "=", False)],
    )
    department_manager_as_approver = fields.Boolean(
        string="Include Department Manager",
        help="Add the selected department's manager as an approver when submitting.",
    )
    require_all_approvers = fields.Boolean(default=True)
    minimum_approvals = fields.Integer(default=1, required=True)
    approver_count = fields.Integer(compute="_compute_approver_count")

    _unique_matrix_sequence = models.Constraint(
        "UNIQUE(matrix_id, sequence)",
        "Each approval sequence can only occur once per matrix.",
    )

    @api.depends("approver_ids")
    def _compute_approver_count(self):
        for stage in self:
            stage.approver_count = len(stage.approver_ids)

    @api.constrains("minimum_approvals", "approver_ids", "require_all_approvers")
    def _check_minimum_approvals(self):
        for stage in self:
            if stage.minimum_approvals < 1:
                raise ValidationError(_("Minimum approvals must be at least one."))
            if (
                not stage.require_all_approvers
                and stage.approver_ids
                and stage.minimum_approvals > len(stage.approver_ids)
            ):
                raise ValidationError(
                    _("Minimum approvals cannot exceed the configured approvers.")
                )

    def effective_approvers(self, department=None):
        self.ensure_one()
        approvers = self.approver_ids
        if self.department_manager_as_approver and department:
            manager_user = department.manager_id.user_id
            if manager_user:
                approvers |= manager_user
        return approvers.filtered(lambda user: user.active and not user.share)

