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


        for vals in vals_list:


            # --------------------------------------------------
            # Set Approval Stage
            # --------------------------------------------------

            if context.get(
                "default_approval_stage"
            ):

                vals.update(
                    {
                        "approval_stage":
                            context.get(
                                "default_approval_stage"
                            )
                    }
                )


            # --------------------------------------------------
            # Set Approval State
            # --------------------------------------------------

            if context.get(
                "default_approval_state"
            ):

                vals.update(
                    {
                        "approval_state":
                            context.get(
                                "default_approval_state"
                            )
                    }
                )


            # --------------------------------------------------
            # Block Manual RFQ / PO Creation
            # Only allowed from Purchase Request
            # --------------------------------------------------

            if (
                not context.get("from_purchase_request")
                and not context.get("install_mode")
                and not context.get("module")
                and not context.get("import_file")
            ):
                raise UserError(
                    _(
                         "Purchase Order / RFQ must be created "
                         "from an approved Purchase Request."
                    )
                )

        orders = super().create(vals_list)

        return orders

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

    # ==========================================================
    # CONFIRM PURCHASE ORDER
    # ==========================================================

    def button_confirm(self):

        for order in self:

            if order.approval_stage == "po":

                if order.approval_state != "approved":

                    raise UserError(
                        _(
                            "Purchase Order must be approved "
                            "before confirmation."
                        )
                    )

        return super().button_confirm()
    
    # ==========================================================
    # APPROVE BUTTON ACTION
    # ==========================================================

    def action_approve(self):

        self.ensure_one()


        self._approval_matrix_approved(
            self.env.user
        )


        return True



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