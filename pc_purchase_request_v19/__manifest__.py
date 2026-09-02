{
    "name": "Purchase Request",
    "summary": "Internal purchase requests with approval and RFQ/PO conversion",
    "version": "19.0.2.0.0",
    "category": "Purchases",
    "author": "Rebuilt for Odoo 19",
    "license": "LGPL-3",

    "depends": [
        "purchase_stock",
        "stock",
        "mail",
        "hr",
        "pc_approval_matrix_v19",
    ],

    "data": [
        "security/purchase_request_security.xml",
        "security/ir.model.access.csv",

        "data/purchase_request_sequence.xml",

        "views/purchase_request_views.xml",
        "views/purchase_order_approval_views.xml",

        "wizard/purchase_request_order_wizard_views.xml",
        "wizard/purchase_request_cancel_wizard_views.xml",

        "views/product_group_category_views.xml",
        "views/purchase_request_menus.xml",
    ],

    "installable": True,
    "application": False,
}