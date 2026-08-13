# Odoo 19 Payment Request Rebuild

This package is a clean Odoo 19 reconstruction of the Odoo 13 Port Cities
`sh_payment_request` and `approval_matrix` workflow found in the supplied
database dump. It does not contain or copy proprietary Port Cities source code.

## Included addons

- `pc_approval_matrix_v19`: configurable approval matrices by company,
  department, and base-currency amount.
- `pc_payment_request_v19`: payment request entry, multi-level approvals,
  rejection reason, audit fields, activities, and paid status.

The payment request addon depends only on standard Odoo modules and the rebuilt
approval addon. It replaces the legacy dependencies `sh_payment_other`,
`sh_exchange_rate_payment`, `web_many2one_reference`, and
`currency_rate_inverted` with standard Odoo 19 functionality.

## Reconstructed legacy behaviour

- Workflow: Draft -> Waiting Approval -> Approved -> Paid.
- Rejection with a mandatory reason and reset to draft.
- Approval matrix matching uses department and amount converted to company
  currency.
- Amount ranges support the legacy boundaries:
  - amount <= RM2,000;
  - RM2,000 < amount <= RM20,000;
  - amount > RM20,000.
- Up to four sequential approval levels.
- Each level can require all configured approvers or a minimum number.
- The department manager can be included dynamically as an approver.
- Chatter, approval activities, submission/approval/rejection audit fields,
  and an optional link to an Accounting Payment.

## Important limitations

- This is a functional reconstruction, not a byte-for-byte port of the
  proprietary Odoo 13 modules.
- The 3,922 old payment request records are not imported automatically.
- Old attachments need the original filestore and are not present in a
  database-only dump.
- Approver users must be mapped to users in the Odoo 19 database.
- Mark Paid records the workflow status. Creating and posting an Accounting
  Payment remains a controlled Finance action; an existing payment can be
  linked on the request.

## Safe Odoo.sh deployment

Do not restore the Odoo 13 dump directly into Odoo 19.

1. Create a new development branch from the Odoo 19 branch, for example
   `payment-request-v19`.
2. Copy both addon folders into the Git repository root or its custom addons
   directory:
   - `pc_approval_matrix_v19`
   - `pc_payment_request_v19`
3. Commit and push the branch:

   ```bash
   git add pc_approval_matrix_v19 pc_payment_request_v19
   git commit -m "Add Odoo 19 payment request approval workflow"
   git push -u origin payment-request-v19
   ```

4. Wait for the Odoo.sh development build to become green.
5. Open the development database, activate developer mode, and select
   Apps -> Update Apps List.
6. Search for and install **PC Payment Request**. The approval matrix addon is
   installed automatically.
7. Assign users under Settings -> Users:
   - Payment Request User;
   - Payment Request Approver;
   - Payment Request Manager.
8. Open Payment Requests -> Configuration -> Approval Matrices.
9. Review the installed fallback matrix. It assigns the Administrator as the
   approver and exists only to make the first test possible.
10. Import or create the real matrices and approval stages. Deactivate the
    fallback matrix before go-live.
11. After development tests pass, merge the branch into a staging branch and
    repeat UAT there.

## Configuration templates

`configuration_templates/approval_matrices.csv` contains the 48 active matrix
combinations reconstructed from the dump: 16 departments multiplied by three
amount ranges.

Import it into the Approval Matrices list after the matching HR departments
exist in Odoo 19. If the target database uses different department names,
replace the `department_id` values before importing.

`configuration_templates/approval_stages_template.csv` is a two-stage example.
Replace `base.user_admin` with the Odoo 19 external IDs of the correct approver
users. Because the dump does not contain the custom source repository and user
mapping decisions are business-sensitive, the old approvers are not hardcoded.

## Minimum UAT

1. Create a request for each amount boundary: RM2,000, RM2,000.01, RM20,000,
   and RM20,000.01.
2. Confirm the correct department matrix is selected.
3. Confirm a future-level approver cannot approve early.
4. Test a level with two or three approvers and Require All enabled.
5. Test a minimum-approval stage with Require All disabled.
6. Reject a request and confirm a reason is mandatory.
7. Reset the rejected request, edit it, and resubmit.
8. Complete all levels and mark the request Paid as a manager.
9. Verify requesters cannot see unrelated requests.
10. Test another company if multi-company is enabled.

## Static validation performed

- Python source parsed successfully.
- XML files parsed successfully.
- Manifest data paths and CSV column consistency are checked by the package
  validation script.

An actual Odoo.sh development build is still required because this workspace
does not contain an Odoo 19 server runtime.
