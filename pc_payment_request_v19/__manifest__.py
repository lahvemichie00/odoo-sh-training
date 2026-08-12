{
    "name": "Payment Request",
    "summary": "Payment requests using the generic approval matrix",
    "version": "19.0.2.0.0",
    "category": "Accounting",
    "author": "Rebuilt for Odoo 19",
    "license": "LGPL-3",
    "depends": ["account", "analytic", "mail", "hr", "pc_approval_matrix_v19"],
    "data": [
        "security/payment_request_security.xml",
        "security/ir.model.access.csv",
        "data/payment_request_data.xml",
        "views/payment_request_views.xml",
        "views/payment_request_menus.xml",
    ],
    "installable": True,
    "application": True,
}
