{
    "name": "PC Payment Request",
    "summary": "Payment requests with sequential approval matrices",
    "version": "19.0.1.0.0",
    "category": "Accounting",
    "author": "Rebuilt for Odoo 19",
    "license": "LGPL-3",
    "depends": ["account", "mail", "pc_approval_matrix_v19"],
    "data": [
        "security/payment_request_security.xml",
        "security/ir.model.access.csv",
        "data/payment_request_sequence.xml",
        "views/payment_request_views.xml",
        "wizard/reject_wizard_views.xml",
        "views/payment_request_menus.xml",
    ],
    "installable": True,
    "application": True,
}

