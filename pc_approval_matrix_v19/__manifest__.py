{
    "name": "PC Approval Matrix",
    "summary": "Configurable department and amount-based approval matrices",
    "version": "19.0.1.0.0",
    "category": "Accounting",
    "author": "Rebuilt for Odoo 19",
    "license": "LGPL-3",
    "depends": ["base", "hr"],
    "data": [
        "security/approval_matrix_security.xml",
        "security/ir.model.access.csv",
        "views/approval_matrix_views.xml",
        "data/default_matrix.xml",
    ],
    "installable": True,
    "application": True,
}

