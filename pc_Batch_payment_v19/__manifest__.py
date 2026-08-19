{
    "name": "Batch Payment Approval",
    "summary": "Approval workflow for Batch Payments using the generic approval matrix",
    "version": "19.0.1.0.0",
    "category": "Accounting",
    "author": "Rebuilt for Odoo 19",
    "license": "LGPL-3",
    "depends": ["account_batch_payment", "mail", "pc_approval_matrix_v19"],
    "data": [
    "security/accounting_security.xml",
    "security/ir.model.access.csv",
    "views/accounting_order_views.xml",
],
    "installable": True,
    "application": False,
}