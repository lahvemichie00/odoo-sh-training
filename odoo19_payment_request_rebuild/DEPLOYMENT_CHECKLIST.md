# Deployment Checklist

## Before push

- [ ] Use a development branch, not the production branch.
- [ ] Copy both addon directories into the Git repository.
- [ ] Confirm the branch is Odoo 19.0.
- [ ] Commit and push.

## Development build

- [ ] Build is green.
- [ ] Apps list updated.
- [ ] PC Payment Request installed.
- [ ] No traceback in install logs.
- [ ] Payment Request groups assigned.
- [ ] First request can be submitted using the fallback matrix.

## Configuration

- [ ] All 16 departments exist.
- [ ] Forty-eight department/amount matrices imported or created.
- [ ] Approvers mapped for every stage.
- [ ] Default Administrator fallback matrix deactivated.
- [ ] Multi-company configuration checked.

## UAT

- [ ] RM2,000 boundary tested.
- [ ] RM20,000 boundary tested.
- [ ] Sequential approval tested.
- [ ] Multiple approvers tested.
- [ ] Rejection and reset tested.
- [ ] Paid status tested.
- [ ] Access rights tested with non-admin users.

## Staging handover

- [ ] Development branch merged into staging.
- [ ] Staging database is neutralized.
- [ ] Email/payment integrations remain disabled for testing.
- [ ] UAT evidence captured.
- [ ] Known limitations communicated.
