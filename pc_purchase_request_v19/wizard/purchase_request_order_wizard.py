from odoo import _, api, fields, models
from odoo.exceptions import UserError


class PurchaseRequestLineMakePurchaseOrder(models.TransientModel):
    _name = "purchase.request.line.make.purchase.order"
    _description = "Purchase Request Line Make Purchase Order"

    supplier_id = fields.Many2one(
        "res.partner",
        string="Supplier",
        required=False,
        domain=[("supplier_rank", ">", 0)],
    )

    purchase_order_id = fields.Many2one(
        "purchase.order",
        string="Purchase Order",
        domain="[('partner_id', '=', supplier_id), ('company_id', '=', company_id), ('state', '=', 'draft')]",
    )

    picking_type_id = fields.Many2one(
        "stock.picking.type",
        string="Picking Type",
        required=True,
        domain="[('code', '=', 'incoming'), ('company_id', 'in', [company_id, False])]",
    )

    group_category_id = fields.Many2one(
        "product.group.category",
        string="Group Category",
    )

    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
    )

    currency_id = fields.Many2one(
        "res.currency",
        required=True,
        default=lambda self: self.env.company.currency_id,
    )

    item_ids = fields.One2many(
        "purchase.request.line.make.purchase.order.item",
        "wiz_id",
        string="Items",
    )

    @api.model
    def default_get(self, fields_list):
        values = super().default_get(fields_list)

        active_ids = self.env.context.get("active_ids", [])

        lines = self.env["purchase.request.line"].browse(active_ids).exists()

        if not lines:
            return values

        lines._validate_for_order()

        company = lines.mapped("company_id")

        if len(company) != 1:
            raise UserError(
                _("Select purchase request lines from one company only.")
            )

        company = company[0]

        picking = self.env["stock.picking.type"].search(
            [
                ("code", "=", "incoming"),
                ("company_id", "in", [company.id, False]),
            ],
            limit=1,
        )

        values.update(
            {
                "company_id": company.id,
                "currency_id": company.currency_id.id,
                "picking_type_id": picking.id,
                "group_category_id": lines[:1].group_category_id.id,
                "item_ids": [
                    (
                        0,
                        0,
                        {
                            "line_id": line.id,
                            "product_id": line.product_id.id,
                            "name": line.desc
                            or line.product_id.display_name,
                            "product_qty": line.qty - line.qty_released,
                            "product_uom_id": line.product_uom_id.id,
                            "price_unit": 0.0,
                        },
                    )
                    for line in lines
                ],
            }
        )

        return values

    @api.onchange("supplier_id")
    def _onchange_supplier_id(self):
        self.purchase_order_id = False

    def action_create_order(self):
        self.ensure_one()

        if not self.item_ids:
            raise UserError(
                _("There are no items to purchase.")
            )

        if self.item_ids.filtered(
            lambda x: x.product_qty <= 0
        ):
            raise UserError(
                _("Purchase quantity must be positive.")
            )

        order = self.purchase_order_id

        if not order:
            order = self.env["purchase.order"].create(
                {
                    "company_id": self.company_id.id,
                    "currency_id": self.currency_id.id,
                    "picking_type_id": self.picking_type_id.id,
                    "approval_stage": "rfq",
                    "approval_state": "draft",
                    "origin": ", ".join(
                        self.item_ids.mapped(
                            "line_id.purchase_request_id.name"
                        )
                    ),
                }
            )

        for item in self.item_ids:

            request_line = item.line_id

            if item.product_qty > (
                request_line.qty - request_line.qty_released
            ):
                raise UserError(
                    _(
                        "Quantity exceeds requested quantity for %s"
                    )
                    % request_line.product_id.display_name
                )

            po_line = self.env["purchase.order.line"].create(
                {
                    "order_id": order.id,
                    "product_id": request_line.product_id.id,
                    "name": item.name,
                    "product_qty": item.product_qty,
                    "product_uom": item.product_uom_id.id,
                    "price_unit": item.price_unit,
                    "date_planned": fields.Datetime.now(),
                    "purchase_request_line_id": request_line.id,
                }
            )

            request_line.purchase_line_ids = [
                (4, po_line.id)
            ]

        # Do not automatically confirm the RFQ.
        # The RFQ must go through the RFQ approval workflow first.

        return {
            "type": "ir.actions.act_window",
            "res_model": "purchase.order",
            "res_id": order.id,
            "view_mode": "form",
        }


class PurchaseRequestLineMakePurchaseOrderItem(models.TransientModel):
    _name = "purchase.request.line.make.purchase.order.item"
    _description = "Purchase Request Line Make Purchase Order Item"

    wiz_id = fields.Many2one(
        "purchase.request.line.make.purchase.order",
        required=True,
        ondelete="cascade",
    )

    line_id = fields.Many2one(
        "purchase.request.line",
        string="Purchase Request Line",
        required=True,
        ondelete="cascade",
    )

    product_id = fields.Many2one(
        related="line_id.product_id",
        readonly=True,
    )

    name = fields.Char(
        string="Description",
        required=True,
    )

    product_qty = fields.Float(
        string="Quantity to purchase",
        required=True,
    )

    product_uom_id = fields.Many2one(
        "uom.uom",
        string="UoM",
        required=True,
    )

    price_unit = fields.Float(
        string="Price",
        default=0.0,
    )