from odoo import _, fields, models
from odoo.exceptions import UserError


class PurchaseRequestCancelWizard(models.TransientModel):
    _name = "purchase.request.cancel.wizard"
    _description = "Purchase Request Cancellation Wizard"

    purchase_request_id = fields.Many2one(
        "purchase.request",
        string="Purchase Request",
        required=True,
        readonly=True,
    )

    cancellation_reason = fields.Text(
        string="Cancellation Reason",
        required=True,
    )

    def action_cancel(self):
        self.ensure_one()

        if not self.purchase_request_id:
            raise UserError(
                _("Purchase Request not found.")
            )

        reason = (self.cancellation_reason or "").strip()

        if not reason:
            raise UserError(
                _("Please provide a cancellation reason.")
            )

        self.purchase_request_id.action_cancel(
            reason=reason
        )

        return {
            "type": "ir.actions.act_window_close",
        }