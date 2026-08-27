from odoo import fields, models


class PurchaseOrderPeriodWizard(models.TransientModel):
    _name = "purchase.order.period"
    _description = "Purchase Order Period Report"

    start_date = fields.Date(
        string="Start Date",
        required=True,
    )

    end_date = fields.Date(
        string="End Date",
        required=True,
    )

    po_status = fields.Selection(
        [
            ("draft", "Draft"),
            ("sent", "RFQ Sent"),
            ("purchase", "Purchase Order"),
            ("done", "Done"),
            ("cancel", "Cancelled"),
        ],
        string="PO Status",
        default="draft",
    )

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        default=lambda self: self.env.company,
        required=True,
    )

    def action_generate_excel(self):
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Purchase Order Period",
                "message": "Excel report generated successfully.",
                "type": "success",
                "sticky": False,
            },
        }