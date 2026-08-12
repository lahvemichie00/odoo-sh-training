{
    "name": "Approval Matrix",
    "summary": "Generic rule-based sequential document approvals",
    "version": "19.0.2.0.0",
    "category": "Productivity",
    "author": "Rebuilt for Odoo 19",
    "license": "LGPL-3",
    "depends": ["base", "mail", "hr"],
    "data": [
        "security/approval_matrix_security.xml",
        "security/ir.model.access.csv",
        "views/approval_matrix_views.xml",
        "wizard/approval_reject_wizard_views.xml",
    ],
    "installable": True,
    "application": True,
}
