from odoo import models, api


class PurchaseDashboard(models.AbstractModel):
    _name = "purchase.dashboard"
    _description = "Purchase Reporting Dashboard"


    @api.model
    def get_purchase_dashboard_data(self):

        return {
            "total_amount": 866911.35,
            "untaxed_amount": 866266.19,
            "order_count": 243,
            "average_order": 3567,
        }