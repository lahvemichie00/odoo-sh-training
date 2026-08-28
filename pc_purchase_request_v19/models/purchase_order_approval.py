from odoo import _, api, fields, models
from odoo.exceptions import UserError


class PurchaseOrder(models.Model):
    _inherit = ["purchase.order", "approval.matrix.mixin"]

    # ==========================================================
    # RFQ REFERENCE
    # ==========================================================

    rfq_number = fields.Char(
        string="RFQ Reference",
        copy=False,
        readonly=True,
        tracking=True,
    )

    # ==========================================================
    # APPROVAL STAGE
    # ==========================================================

    approval_stage = fields.Selection(
        [
            ("rfq", "RFQ"),
            ("po", "Purchase Order"),
        ],
        string="Approval Stage",
        default="rfq",
        required=True,
        copy=False,
        tracking=True,
    )

    # ==========================================================
    # APPROVAL STATUS
    # ==========================================================

    approval_state = fields.Selection(
        [
            ("draft", "Draft"),
            ("waiting_approval", "To Approve"),
            ("approved", "Approved"),
            ("rejected", "Rejected"),
        ],
        string="Approval Status",
        default="draft",
        required=True,
        copy=False,
        tracking=True,
    )

    # ==========================================================
    # CREATE
    # ==========================================================

    @api.model_create_multi
    def create(self, vals_list):
        """
        Prevent normal Purchase Users from creating RFQs/POs
        directly.

        Purchase documents must be created through the
        approved Purchase Request workflow.

        Purchase Managers can still create documents directly.
        Internal Purchase Request workflow is allowed through
        the `from_purchase_request` context.
        """

        # ------------------------------------------------------
        # BLOCK DIRECT RFQ / PO CREATION
        # ------------------------------------------------------

        if (
            not self.env.context.get("from_purchase_request")
            and not self.env.user.has_group(
                "purchase.group_purchase_manager"
            )
            and not self.env.context.get("install_demo")
        ):
            raise UserError(
                _(
                    "Purchase Orders and RFQs must be created "
                    "through an approved Purchase Request."
                )
            )

        # ------------------------------------------------------
        # GENERATE RFQ REFERENCE
        # ------------------------------------------------------

        for vals in vals_list:

            approval_stage = vals.get("approval_stage", "rfq")

            # Generate RFQ number only for RFQ stage.
            #
            # No RFQ number is generated for Purchase Order stage.

            if (
                approval_stage == "rfq"
                and not vals.get("rfq_number")
            ):
                company = self.env["res.company"].browse(
                    vals.get("company_id") or self.env.company.id
                )

                vals["rfq_number"] = (
                    self.env["ir.sequence"]
                    .with_company(company)
                    .next_by_code("purchase.request.rfq")
                    or _("New")
                )

        return super().create(vals_list)

    # ==========================================================
    # SUBMIT FOR APPROVAL
    # ==========================================================

    def action_submit_for_approval(self):
        for order in self:

            if order.approval_state != "draft":
                raise UserError(
                    _(
                        "Only draft documents can be submitted "
                        "for approval."
                    )
                )

            order._approval_refresh(replace=True)

            order.with_context(
                skip_purchase_approval_workflow=True
            ).write(
                {
                    "approval_state": "waiting_approval",
                }
            )

            order.message_post(
                body=_(
                    "%s submitted for approval."
                )
                % (
                    "RFQ"
                    if order.approval_stage == "rfq"
                    else "Purchase Order"
                )
            )

        return True

    # ==========================================================
    # APPROVE
    # ==========================================================

    def action_approve(self):
        for order in self:

            if order.approval_state != "waiting_approval":
                raise UserError(
                    _(
                        "This document is not waiting "
                        "for approval."
                    )
                )

        return self._approval_action_approve()

    # ==========================================================
    # CONFIRM
    # ==========================================================

    def button_confirm(self):
        """
        Control RFQ and Purchase Order confirmation.

        RFQ:
        - RFQ must be approved first.
        - After RFQ approval, the document moves to PO
          approval stage.
        - RFQ is NOT immediately confirmed.

        PO:
        - PO must be approved before confirmation.
        """

        # ------------------------------------------------------
        # ALLOW ODOO DEMO INSTALLATION
        # ------------------------------------------------------

        if self.env.context.get("install_demo"):
            return super().button_confirm()

        # ------------------------------------------------------
        # VALIDATE EACH ORDER
        # ------------------------------------------------------

        for order in self:

            # ==================================================
            # RFQ STAGE
            # ==================================================

            if order.approval_stage == "rfq":

                if order.approval_state != "approved":
                    raise UserError(
                        _(
                            "This RFQ must be approved before "
                            "it can proceed to Purchase Order "
                            "approval."
                        )
                    )

                # --------------------------------------------------
                # RFQ APPROVED
                # Move to PO approval stage.
                # --------------------------------------------------

                order.with_context(
                    skip_purchase_approval_workflow=True
                ).write(
                    {
                        "approval_stage": "po",
                        "approval_state": "draft",
                    }
                )

                order.message_post(
                    body=_(
                        "RFQ approved. The document is now "
                        "ready for Purchase Order approval."
                    )
                )

                # Do NOT confirm yet.
                continue

            # ==================================================
            # PO STAGE
            # ==================================================

            if order.approval_stage == "po":

                if order.approval_state != "approved":
                    raise UserError(
                        _(
                            "This Purchase Order must be "
                            "approved before confirmation."
                        )
                    )

        # ------------------------------------------------------
        # ONLY APPROVED PO REACHES ODOO CONFIRMATION
        # ------------------------------------------------------

        return super().button_confirm()

    # ==========================================================
    # APPROVAL LEVEL
    # ==========================================================

    def _approval_level_approved(self, user, approval):
        return True

    # ==========================================================
    # APPROVAL MATRIX APPROVED
    # ==========================================================

    def _approval_matrix_approved(self, user):

        for order in self:

            # ==================================================
            # RFQ APPROVAL
            # ==================================================

            if order.approval_stage == "rfq":

                order.with_context(
                    skip_purchase_approval_workflow=True
                ).write(
                    {
                        "approval_state": "approved",
                    }
                )

                order.message_post(
                    body=_(
                        "RFQ approved by %s. "
                        "The document can now proceed to "
                        "Purchase Order approval."
                    )
                    % user.display_name
                )

            # ==================================================
            # PO APPROVAL
            # ==================================================

            elif order.approval_stage == "po":

                order.with_context(
                    skip_purchase_approval_workflow=True
                ).write(
                    {
                        "approval_state": "approved",
                    }
                )

                order.message_post(
                    body=_(
                        "Purchase Order approved by %s."
                    )
                    % user.display_name
                )

    # ==========================================================
    # APPROVAL MATRIX REJECTED
    # ==========================================================

    def _approval_matrix_rejected(self, user, reason):

        self.with_context(
            skip_purchase_approval_workflow=True
        ).write(
            {
                "approval_state": "rejected",
            }
        )

        self.message_post(
            body=_(
                "Purchase document rejected by %(user)s. "
                "Reason: %(reason)s"
            )
            % {
                "user": user.display_name,
                "reason": reason,
            }
        )