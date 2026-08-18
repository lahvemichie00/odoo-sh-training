from odoo import models, fields


class ProductGroupCategory(models.Model):
    _name = "product.group.category"
    _description = "Product Group Category"
    _order = "name"

    name = fields.Char(
        string="Group Category",
        required=True,
        index=True,
    )

    active = fields.Boolean(
        string="Active",
        default=True,
    )

    description = fields.Text(
        string="Description",
    )