from odoo import _, fields, models
from odoo.exceptions import UserError


class PcPaymentRequestRejectWizard(models.TransientModel):
    _name = "pc.payment.request.reject.wizard"
    _description = "Reject Payment Request"

    request_id = fields.Many2one(
        "pc.payment.request",
        required=True,
        readonly=True,
    )
    reason = fields.Text(required=True)

    def action_reject(self):
        self.ensure_one()
        if not self.reason or not self.reason.strip():
            raise UserError(_("Enter a rejection reason."))
        self.request_id._action_reject(self.reason.strip())
        return {"type": "ir.actions.act_window_close"}

