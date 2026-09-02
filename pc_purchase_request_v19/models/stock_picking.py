from odoo import _, models
from odoo.exceptions import UserError


class StockPicking(models.Model):

    _inherit = "stock.picking"


    def button_validate(self):

        for picking in self:

            if picking.purchase_id:

                purchase = picking.purchase_id

                if purchase.approval_stage != "po":

                    raise UserError(
                        _(
                            "Only Purchase Order can create receipt."
                        )
                    )

                if purchase.approval_state != "approved":

                    raise UserError(
                        _(
                            "Purchase Order must be approved before receiving."
                        )
                    )

        return super().button_validate()
    