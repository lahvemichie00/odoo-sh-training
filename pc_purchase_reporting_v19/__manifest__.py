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
        "views/purchase_dashboard_views.xml",
    ],

    "assets": {
        "web.assets_backend": [
            "pc_purchase_reporting_v19/static/src/components/purchase_reporting_dashboard.js",
            "pc_purchase_reporting_v19/static/src/xml/purchase_reporting_dashboard.xml",
        ],
    },

    "installable": True,
    "application": False,
    "license": "LGPL-3",
}