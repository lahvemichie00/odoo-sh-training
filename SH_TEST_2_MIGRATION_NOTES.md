# Migration decisions and known boundaries

## Preserved from Odoo 13

- Original business model names for Approval Matrix, Payment Request and Purchase Request.
- Generic approval rules, sequential levels, multi-user levels, require-all/minimum logic,
  approved/rejected users and approval counts.
- Payment Request and Purchase Request status labels, tabs, main fields and audit fields.
- Purchase Request Line list actions and linkage to Purchase Order Line.

## Necessary Odoo 19 adaptations

1. The removed `web_many2one_reference` dependency is not used. Document Approval keeps
   the original `res_model` plus `res_id` reference using the Odoo 19 ORM.
2. Base-currency approval matching uses Odoo 19 native currency conversion. The unavailable
   Odoo 13 `currency_rate_inverted` and Port Cities exchange-rate modules are not copied.
3. `Create RFQ` creates the native Odoo 19 draft `purchase.order`. Odoo 13 also had a custom
   `product.supplier.quotation` workflow whose source code was not present in the backup.
4. `Create PO` uses the same wizard and confirms the native purchase order after creation.
5. The Payment Voucher checkbox is derived from linked non-draft payments. The Odoo 13
   database contained the payment link but no stored `payment_voucher` column.

## Deliberately excluded

- Production business records are not restored into an Odoo 19 development database.
- Approval configuration is not guessed. Exact matrix, rule and approver data must be
  imported only after it is extracted and mapped by external IDs/names.
- No Cancel, Reset to Draft or manual Mark Paid buttons were added to Payment Request.
