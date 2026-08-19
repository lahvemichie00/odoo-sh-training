from odoo import models, api


class PurchaseDashboard(models.AbstractModel):
    _name = "purchase.dashboard"
    _description = "Purchase Reporting Dashboard"


    @api.model
    def get_purchase_dashboard_data(self):

        return {

            # KPI
            "total_amount": 866911.35,
            "untaxed_amount": 866266.19,
            "order_count": 243,
            "average_order": 3567,


            # Chart
            "chart_labels": [
                "01 Aug",
                "05 Aug",
                "10 Aug",
                "15 Aug",
                "19 Aug",
            ],

            "chart_values": [
                50000,
                120000,
                80000,
                200000,
                150000,
            ],

        }