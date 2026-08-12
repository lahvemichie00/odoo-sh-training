from odoo import _, api, fields, models
from odoo.exceptions import UserError


class ApprovalMatrixRejectWizard(models.TransientModel):
    _name = "approval.matrix.reject.wizard"
    _description = "Reject Approval Document"

    res_model = fields.Char(required=True, readonly=True)
    res_id = fields.Integer(required=True, readonly=True)
    reason_id = fields.Many2one(
        "rejection.message",
        string="Rejection Message",
        domain="[('res_model', 'in', [res_model, False])]",
    )
    reason = fields.Text(required=True)

    @api.onchange("reason_id")
    def _onchange_reason_id(self):
        if self.reason_id:
            self.reason = self.reason_id.name

    def action_reject(self):
        self.ensure_one()
        if self.res_model not in self.env:
            raise UserError(_("The related document model is unavailable."))
        document = self.env[self.res_model].browse(self.res_id).exists()
        if not document:
            raise UserError(_("The related document no longer exists."))
        document._approval_action_reject(self.reason)
        return {"type": "ir.actions.act_window_close"}
