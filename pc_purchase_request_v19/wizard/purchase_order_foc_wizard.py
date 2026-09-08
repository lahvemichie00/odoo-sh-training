from odoo import _, fields, models
from odoo.exceptions import UserError


class PurchaseOrderFocWizard(models.TransientModel):

    _name = "purchase.order.foc.wizard"
    _description = "Add Free Of Charge Product"


    purchase_order_id = fields.Many2one(
        "purchase.order",
        string="Purchase Order",
        required=True,
    )


    product_id = fields.Many2one(
        "product.product",
        string="Product",
        required=True,
    )


    quantity = fields.Float(
        string="Quantity",
        default=1.0,
        required=True,
    )


    def action_add_foc_line(self):

        self.ensure_one()


        if not self.purchase_order_id:

            raise UserError(
                _("Purchase Order is missing.")
            )


        if self.quantity <= 0:

            raise UserError(
                _("FOC quantity must be greater than zero.")
            )


        order = self.purchase_order_id


        order.order_line.create({

            "order_id":
                order.id,


            "product_id":
                self.product_id.id,


            "name":
                "FOC - %s"
                % self.product_id.display_name,


            "product_qty":
                self.quantity,


            "product_uom":
                self.product_id.uom_id.id,


            "price_unit":
                0.0,


            "is_foc": True,


            "taxes_id":
                [(6, 0, [])],


        })


        order.message_post(
            body=_(
                "FOC product added: %s (%s qty)"
            )
            % (
                self.product_id.display_name,
                self.quantity,
            )
        )


        return {
            "type": "ir.actions.act_window_close"
        }