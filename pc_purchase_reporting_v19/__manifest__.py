{
    "name": "Purchase Reporting Extension",
    "version": "19.0.1.0.0",
    "category": "Purchase",
    "summary": "Custom Purchase Reporting Period Export",

    "depends": [
        "purchase",
    ],

    "data": [
        "security/ir.model.access.csv",
        "views/purchase_report_views.xml",
        "views/purchase_order_period_views.xml",
    ],

    "installable": True,
    "application": False,
    "license": "LGPL-3",
}