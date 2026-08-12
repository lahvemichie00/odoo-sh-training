# Sanctuary Health Odoo 19 Rebuild

Clean Odoo 19 rebuild for the `SH-test-2` branch.

## Modules

1. `pc_approval_matrix_v19`
   - Generic model/field/operator/value rules.
   - Sequential approver levels, all/minimum approver logic.
   - Document Approval history and notification action.
   - Rejection Message configuration.
2. `pc_payment_request_v19`
   - Original technical model `payment.request.order` and line model.
   - Draft, Waiting Approval, Approved, Paid and Rejected states.
   - Payment Request Line, Other Information and Approvals tabs.
   - Paid status is set when a linked `account.payment` is posted.
3. `pc_purchase_request_v19`
   - Original technical model `purchase.request` and line model.
   - Added below the standard Odoo Purchase app.
   - Draft, Waiting Approval, Approved and Reject states.
   - Create RFQ, Create PO and Cancel list actions.

## Install order

Install `Approval Matrix`, then `Payment Request`, then `Purchase Request`.

No approval matrices are installed automatically. This prevents a permissive fallback
matrix from changing the source company's approval control. Configure or import the
verified matrices before submitting test documents.
