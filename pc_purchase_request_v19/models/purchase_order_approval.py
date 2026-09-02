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
    # SOURCE RFQ (FOR CONVERTED PO)
    # ==========================================================

    source_rfq_id = fields.Many2one(
        "purchase.order",
        string="Source RFQ",
        readonly=True,
        copy=False,
        ondelete="set null",
    )
    
    # ==========================================================
    # CONVERTED PURCHASE ORDER SMART BUTTON
    # ==========================================================

    converted_po_ids = fields.One2many(
        "purchase.order",
        "source_rfq_id",
        string="Converted Purchase Orders",
    )


    converted_po_count = fields.Integer(
        string="Purchase Order Count",
        compute="_compute_converted_po_count",
    )


    @api.depends("converted_po_ids")
    def _compute_converted_po_count(self):

        for order in self:

            order.converted_po_count = len(
                order.converted_po_ids
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


    # ==========================================================
    # COMPUTE PURCHASE REQUEST
    # ==========================================================

    @api.depends("order_line.purchase_request_line_id")
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
    # OPEN SOURCE RFQ
    # ==========================================================

    def action_open_source_rfq(self):

        self.ensure_one()


        if not self.source_rfq_id:
            return False


        return {
            "type": "ir.actions.act_window",
            "name": _("RFQ"),
            "res_model": "purchase.order",
            "view_mode": "form",
            "res_id": self.source_rfq_id.id,
            "target": "current",
        }

    # ==========================================================
    # OPEN CONVERTED PURCHASE ORDER
    # ==========================================================

    def action_open_converted_purchase_orders(self):

        self.ensure_one()

        orders = self.converted_po_ids


        if not orders:
            return False


        if len(orders) == 1:

            return {
                "type": "ir.actions.act_window",
                "name": _("Purchase Order"),
                "res_model": "purchase.order",
                "view_mode": "form",
                "res_id": orders.id,
                "target": "current",
            }


        return {
            "type": "ir.actions.act_window",
            "name": _("Purchase Orders"),
            "res_model": "purchase.order",
            "view_mode": "list,form",
            "domain": [
                ("id", "in", orders.ids),
            ],
            "target": "current",
        }

    # ==========================================================
    # CONVERT RFQ TO PO
    # ==========================================================

    def action_convert_to_po(self):

        self.ensure_one()

        if self.approval_stage != "rfq":
            raise UserError(
                _("Only RFQ can be converted to Purchase Order.")
            )

        if self.approval_state != "approved":
            raise UserError(
                _("RFQ must be approved before converting to PO.")
            )

        po = self.with_context(
            from_purchase_request=True
        ).copy(
            {
                "approval_stage": "po",
                "approval_state": "draft",
                "source_rfq_id": self.id,
                "rfq_number": False,
                "origin": self.name,
                "approval_document_ids": False,
            }
        )


        # ------------------------------------------------------
        # Link Purchase Request Line
        # ------------------------------------------------------

        for old_line, new_line in zip(
            self.order_line,
            po.order_line,
        ):
            new_line.purchase_request_line_id = (
                old_line.purchase_request_line_id.id
            )


        # Create NEW approval chain for PO
        po._approval_refresh(
            replace=True
        )


        po.message_post(
            body=_(
                "Purchase Order created from RFQ %s."
            )
            % self.display_name
        )


        return {
            "type": "ir.actions.act_window",
            "name": _("Purchase Order"),
            "res_model": "purchase.order",
            "view_mode": "form",
            "res_id": po.id,
            "target": "current",
        }
    

    # ==========================================================
    # CREATE PURCHASE ORDER / RFQ
    # ==========================================================

    @api.model
    def create(self, vals):

        context = self.env.context


        # --------------------------------------------------
        # Set Approval Stage
        # --------------------------------------------------

        if context.get("default_approval_stage"):
            vals.update({
                "approval_stage": context.get(
                    "default_approval_stage"
                )
            })


        # --------------------------------------------------
        # Set Approval State
        # --------------------------------------------------

        if context.get("default_approval_state"):
            vals.update({
                "approval_state": context.get(
                    "default_approval_state"
                )
            })


        # --------------------------------------------------
        # Block Manual RFQ / PO Creation
        # --------------------------------------------------

        if not context.get("from_purchase_request"):

            raise UserError(
                _(
                    "Purchase Order / RFQ must be created "
                    "from Purchase Request."
                )
            )
        order = super().create(vals)

        return order
    
    # ==========================================================
    # CONFIRM PURCHASE ORDER / RFQ
    # ==========================================================

    def button_confirm(self):

        for order in self:

            if order.approval_state != "approved":
                raise UserError(
                    _(
                        "Purchase document must be approved before confirmation."
                    )
                )

        return super().button_confirm()

    # ==========================================================
    # SUBMIT FOR APPROVAL
    # ==========================================================

    def action_submit_for_approval(self):

        for order in self:

            if order.approval_state != "draft":
                raise UserError(
                    _("Only draft RFQ/PO can be submitted for approval.")
                )

            order._approval_refresh(
                replace=True
            )

            order.write({
                "approval_state": "waiting_approval"
            })

            order.message_post(
                body=_(
                    "Purchase document submitted for approval."
                )
            )

        return True

    # ==========================================================
    # APPROVAL COMPLETED
    # ==========================================================

    def _approval_matrix_approved(self, user):

        for order in self:

            order.write({
                "approval_state": "approved",
            })

            order.message_post(
                body=_(
                    "Purchase document approved by %s."
                )
                % user.name
            )

        return True

    # ==========================================================
    # APPROVAL REJECTED
    # ==========================================================

    def _approval_matrix_rejected(self, user, reason):

        for order in self:

            order.write({
                "approval_state": "rejected",
            })

            order.message_post(
                body=_(
                    "Purchase document rejected by %s.<br/>Reason: %s"
                )
                % (
                    user.name,
                    reason,
                )
            )

        return True
    