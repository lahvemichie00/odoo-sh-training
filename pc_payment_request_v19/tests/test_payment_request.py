from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestPcPaymentRequest(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.env.ref(
            "pc_approval_matrix_v19.matrix_default_payment_request"
        ).active = False
        cls.department = cls.env["hr.department"].create(
            {"name": "Payment Request Test", "company_id": cls.company.id}
        )
        user_group = cls.env.ref("pc_payment_request_v19.group_payment_request_user")
        cls.approver_one = cls.env["res.users"].with_context(no_reset_password=True).create(
            {
                "name": "PR Approver One",
                "login": "pr-approver-one@example.test",
                "email": "pr-approver-one@example.test",
                "company_id": cls.company.id,
                "company_ids": [(6, 0, [cls.company.id])],
                "group_ids": [(6, 0, [user_group.id])],
            }
        )
        cls.approver_two = cls.env["res.users"].with_context(no_reset_password=True).create(
            {
                "name": "PR Approver Two",
                "login": "pr-approver-two@example.test",
                "email": "pr-approver-two@example.test",
                "company_id": cls.company.id,
                "company_ids": [(6, 0, [cls.company.id])],
                "group_ids": [(6, 0, [user_group.id])],
            }
        )
        cls.matrix = cls.env["pc.approval.matrix"].create(
            {
                "name": "Test Matrix",
                "company_id": cls.company.id,
                "department_id": cls.department.id,
                "minimum_amount": 0,
                "minimum_inclusive": True,
                "has_maximum": True,
                "maximum_amount": 20000,
                "maximum_inclusive": True,
                "stage_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Department Approval",
                            "sequence": 0,
                            "approver_ids": [(6, 0, [cls.approver_one.id])],
                        },
                    ),
                    (
                        0,
                        0,
                        {
                            "name": "Finance Approval",
                            "sequence": 1,
                            "approver_ids": [(6, 0, [cls.approver_two.id])],
                        },
                    ),
                ],
            }
        )
        cls.vendor = cls.env["res.partner"].create({"name": "Test Vendor"})

    def _create_request(self, amount=1000):
        return self.env["pc.payment.request"].create(
            {
                "department_id": self.department.id,
                "partner_id": self.vendor.id,
                "payment_details": "Testing sequential approval",
                "line_ids": [(0, 0, {"name": "Test payment", "amount": amount})],
            }
        )

    def test_sequential_approval(self):
        request = self._create_request()
        request.action_submit()

        self.assertEqual(request.state, "waiting_approval")
        self.assertEqual(request.matrix_id, self.matrix)
        self.assertTrue(request.with_user(self.approver_one).can_current_user_approve)
        self.assertFalse(request.with_user(self.approver_two).can_current_user_approve)

        request.with_user(self.approver_one).action_approve()
        self.assertEqual(request.state, "waiting_approval")
        self.assertTrue(request.with_user(self.approver_two).can_current_user_approve)

        request.with_user(self.approver_two).action_approve()
        self.assertEqual(request.state, "approved")

    def test_matrix_amount_boundary(self):
        self.assertEqual(
            self.env["pc.approval.matrix"].find_matrix(
                self.department, 20000, self.company
            ),
            self.matrix,
        )
        self.assertFalse(
            self.env["pc.approval.matrix"].find_matrix(
                self.department, 20000.01, self.company
            )
        )
