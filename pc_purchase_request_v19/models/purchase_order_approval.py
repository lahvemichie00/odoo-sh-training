from odoo import _, api, fields, models
from odoo.exceptions import UserError


class PurchaseOrder(models.Model):

    _inherit = [
        "purchase.order",
        "approval.matrix.mixin",
    ]

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
    # PURCHASE REQUEST SMART BUTTON
    # ==========================================================

    purchase_request_ids = fields.Many2many(
        "purchase.request",
        compute="_compute_purchase_request_ids",
        string="Purchase Requests",
    )


    purchase_request_count = fields.Integer(
        string="Purchase Request Count",
        compute="_compute_purchase_request_ids",
    )



    @api.depends(
        "order_line.purchase_request_line_id"
    )
    def _compute_purchase_request_ids(self):

        for order in self:

            requests = (
                order.order_line
                .mapped("purchase_request_line_id")
                .mapped("purchase_request_id")
            )

            order.purchase_request_ids = requests
            order.purchase_request_count = len(requests)



    # ==========================================================
    # OPEN PURCHASE REQUEST
    # ==========================================================

    def action_open_purchase_requests(self):

        self.ensure_one()

        requests = (
            self.order_line
            .mapped("purchase_request_line_id")
            .mapped("purchase_request_id")
        )


        if not requests:
            return False


        if len(requests) == 1:

            return {
                "type": "ir.actions.act_window",
                "name": _("Purchase Request"),
                "res_model": "purchase.request",
                "view_mode": "form",
                "res_id": requests.id,
                "target": "current",
            }


        return {
            "type": "ir.actions.act_window",
            "name": _("Purchase Requests"),
            "res_model": "purchase.request",
            "view_mode": "list,form",
            "domain": [
                ("id", "in", requests.ids),
            ],
            "target": "current",
        }

    # ==========================================================
    # CREATE PURCHASE ORDER / RFQ
    # ==========================================================

    @api.model_create_multi
    def create(self, vals_list):

        context = self.env.context

        # ======================================================
        # BLOCK MANUAL RFQ / PO CREATION
        # ONLY FROM PURCHASE REQUEST
        # ======================================================

        if (
            not context.get("from_purchase_request")
            and not context.get("install_demo")
            and not self.env.context.get("module_uninstall")
        ):

            raise UserError(
                _("Purchase Order / RFQ must be created from Purchase Request.")
            )


        # ======================================================
        # APPLY APPROVAL VALUES FROM CONTEXT
        # ======================================================

        for vals in vals_list:


            # --------------------------------------------------
            # Approval Stage
            # --------------------------------------------------

            if context.get(
                "default_approval_stage"
            ):

                vals["approval_stage"] = (
                    context.get(
                        "default_approval_stage"
                    )
                )


            # --------------------------------------------------
            # Approval State
            # --------------------------------------------------

            if context.get(
                "default_approval_state"
            ):

                vals["approval_state"] = (
                    context.get(
                        "default_approval_state"
                    )
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
                        "Only draft RFQ/PO can be "
                        "submitted for approval."
                    )
                )


            order.write(
                {
                    "approval_state":
                        "waiting_approval"
                }
            )


            order._approval_refresh(
                replace=True
            )


            order.message_post(
                body=_(
                    "Purchase document submitted "
                    "for approval."
                )
            )


        return True

    def action_approve(self):

        self.ensure_one()

        if self.approval_state != "waiting_approval":
            raise UserError(
                _("Purchase Order is not waiting for approval.")
            )

        return self._approval_action_approve()

    # ==========================================================
    # CONFIRM PURCHASE ORDER
    # ==========================================================

    def button_confirm(self):

        if self.env.context.get('install_demo'):
            return super().button_confirm()

        for order in self:
            if order.approval_state != 'approved':
                raise UserError(
                    _("Purchase document must be approved before confirmation.")
                )

        return super().button_confirm()
    

    # ==========================================================
    # APPROVAL COMPLETED
    # ==========================================================

    def _approval_matrix_approved(
        self,
        user,
    ):


        for order in self:


            order.write(
                {
                    "approval_state":
                        "approved"
                }
            )


            order.message_post(
                body=_(
                    "Purchase document approved "
                    "by %s."
                )
                % user.name
            )


        return True



    # ==========================================================
    # APPROVAL REJECTED
    # ==========================================================

    def _approval_matrix_rejected(
        self,
        user,
        reason,
    ):


        for order in self:


            order.write(
                {
                    "approval_state":
                        "rejected"
                }
            )


            order.message_post(
                body=_(
                    "Purchase document rejected "
                    "by %s.<br/>Reason: %s"
                )
                % (
                    user.name,
                    reason,
                )
            )


        return True