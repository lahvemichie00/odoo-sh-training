from odoo import fields, models


class ProductGroupCategory(models.Model):
    _name = "product.group.category"
    _description = "Group Category of Product"
    _order = "name"

    name = fields.Char(
        string="Group Category",
        required=True,
    )

    active = fields.Boolean(
        default=True,
    )

    description = fields.Text(
        string="Description",
    )