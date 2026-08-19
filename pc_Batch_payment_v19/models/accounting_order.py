from odoo import _, api, fields, models
from odoo.exceptions import UserError


class AccountBatchPayment(models.Model):
    _inherit = ["account.batch.payment", "mail.thread", "mail.activity.mixin", "approval.matrix.mixin"]
    _name = "account.batch.payment"

    approval_state = fields.Selection(
        [
            ("new", "New"),
            ("to_approve", "To Approve"),
            ("approved", "Approved"),
            ("rejected", "Rejected"),
        ],
        string="Approval Status",
        default="new",
        required=True,
        copy=False,
        index=True,
        tracking=True,
    )
    submitted_by_id = fields.Many2one("res.users", string="Submitted By", readonly=True)
    approved_by_id = fields.Many2one("res.users", string="Approved By", readonly=True)
    rejected_by_id = fields.Many2one("res.users", string="Rejected By", readonly=True)
    date_submitted = fields.Datetime(string="Submitted Date", readonly=True)
    date_approved = fields.Datetime(string="Approved Date", readonly=True)
    date_rejected = fields.Datetime(string="Rejected Date", readonly=True)
    reject_reason = fields.Text(string="Reject Reason", readonly=True)

    partner_ids = fields.Many2many(
        "res.partner",
        string="Vendor Name",
        domain=[("supplier_rank", ">", 0)],
    )

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for record in records:
            record.message_post(body=_("Batch Payment Approval Matrix created."))
        return records

    def write(self, values):
        if values.get("state") == "sent" and not self.env.context.get("skip_approval_lock"):
            blocked = self.filtered(lambda batch: batch.approval_state != "approved")
            if blocked:
                raise UserError(
                    _("This batch payment must be approved before it can be sent.")
                )
        return super().write(values)

    def action_submit_for_approval(self):
        for batch in self:
            if batch.approval_state not in ("new", "rejected"):
                raise UserError(
                    _("Only new or rejected batch payments can be submitted for approval.")
                )

            batch._approval_refresh(replace=True)

            batch.write(
                {
                    "approval_state": "to_approve",
                    "submitted_by_id": self.env.user.id,
                    "date_submitted": fields.Datetime.now(),
                    "approved_by_id": False,
                    "date_approved": False,
                    "rejected_by_id": False,
                    "date_rejected": False,
                    "reject_reason": False,
                }
            )
        return True

    def action_reset_to_new(self):
        for batch in self:
            if batch.approval_state not in ("to_approve", "rejected"):
                raise UserError(
                    _("Only batch payments waiting for approval or rejected can be reset.")
                )
            batch.write(
                {
                    "approval_state": "new",
                    "submitted_by_id": False,
                    "date_submitted": False,
                }
            )
            batch.message_post(
                body=_("Approval Status reset to New by %(user)s.")
                % {"user": self.env.user.display_name}
            )
        return True

    def action_approve(self):
        if self.filtered(lambda batch: batch.approval_state != "to_approve"):
            raise UserError(_("The batch payment is not waiting for approval."))
        return self._approval_action_approve()

    def _approval_matrix_approved(self, user):
        self.write(
            {
                "approval_state": "approved",
                "approved_by_id": user.id,
                "date_approved": fields.Datetime.now(),
            }
        )
        self.message_post(body=_("Batch Payment approved by %(user)s.") % {"user": user.name})

    def _approval_matrix_rejected(self, user, reason):
        self.write(
            {
                "approval_state": "rejected",
                "rejected_by_id": user.id,
                "date_rejected": fields.Datetime.now(),
                "reject_reason": reason,
            }
        )
        self.message_post(
            body=_("Batch Payment rejected by %(user)s. Reason: %(reason)s")
            % {"user": user.display_name, "reason": reason}
        )