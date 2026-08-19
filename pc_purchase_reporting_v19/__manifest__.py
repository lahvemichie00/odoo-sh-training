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

        "views/purchase_dashboard_views.xml",
        "views/purchase_reporting_menu_views.xml",
        "views/purchase_report_views.xml",
        "views/purchase_order_period_views.xml",

    ],





    "assets": {

        "web.assets_backend": [


            # Dashboard JS

            "pc_purchase_reporting_v19/static/src/components/purchase_reporting_dashboard.js",




            # Chart JS

            "pc_purchase_reporting_v19/static/src/components/purchase_chart.js",

            "pc_purchase_reporting_v19/static/src/components/purchase_vendor_chart.js",

            "pc_purchase_reporting_v19/static/src/components/purchase_category_chart.js",





            # Dashboard XML

            "pc_purchase_reporting_v19/static/src/xml/purchase_reporting_dashboard.xml",





            # Chart XML

            "pc_purchase_reporting_v19/static/src/xml/purchase_chart.xml",

            "pc_purchase_reporting_v19/static/src/xml/purchase_vendor_chart.xml",

            "pc_purchase_reporting_v19/static/src/xml/purchase_category_chart.xml",


        ],

    },




    "installable": True,

    "application": False,

    "license": "LGPL-3",

}