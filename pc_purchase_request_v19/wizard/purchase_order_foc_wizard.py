from odoo import fields, models, _


class PurchaseOrderFocWizard(models.TransientModel):

    _name = "purchase.order.foc.wizard"
    _description = "Add FOC Product"


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
        default=1,
    )


    def action_add_foc(self):

        self.ensure_one()

        self.env["purchase.order.line"].create(
            {
                "order_id": self.purchase_order_id.id,

                "product_id": self.product_id.id,

                "name": self.product_id.display_name,

                "product_qty": self.quantity,

                "price_unit": 0,

                "is_foc": True,
            }
        )

        return {
            "type": "ir.actions.act_window_close"
        }