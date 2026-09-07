from odoo import _, api, fields, models
from odoo.exceptions import UserError


class PurchaseOrder(models.Model):

    _inherit = [
        "purchase.order",
        "approval.matrix.mixin",
    ]

    partner_id = fields.Many2one(
        "res.partner",
        string="Vendor",
        required=False,
        tracking=True,
    )

    # ==========================================================
    # PURCHASE DOCUMENT TYPE
    # ==========================================================

    purchase_document_type = fields.Selection(
        [
            ("rfq", "RFQ"),
            ("po", "Purchase Order"),
        ],
        string="Purchase Document Type",
        default="rfq",
        required=True,
        copy=False,
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

    source_rfq_id = fields.Many2one(
        "purchase.order",
        string="Source RFQ",
        readonly=True,
        copy=False,
    )

    rfq_count = fields.Integer(
        string="RFQ",
        compute="_compute_document_counts",
    )


    po_count = fields.Integer(
        string="Purchase Orders",
        compute="_compute_document_counts",
    )


    # ==========================================================
    # COMPUTE PURCHASE REQUEST LINK
    # ==========================================================

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
    # COMPUTE RFQ / PO SMART BUTTON COUNT
    # ==========================================================

    @api.depends(
        "purchase_request_ids"
    )
    def _compute_document_counts(self):

        for order in self:

            documents = self.env["purchase.order"].search(
                [
                    (
                        "purchase_request_ids",
                        "in",
                        order.purchase_request_ids.ids,
                    )
                ]
            )


            order.rfq_count = len(
                documents.filtered(
                    lambda x:
                    x.purchase_document_type == "rfq"
                )
            )


            order.po_count = len(
                documents.filtered(
                    lambda x:
                    x.purchase_document_type == "po"
                )
            )


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
    # OPEN RFQ SMART BUTTON
    # ==========================================================

    def action_open_rfqs(self):

        self.ensure_one()

        rfqs = self.env["purchase.order"].search(
            [
                (
                    "purchase_request_ids",
                    "in",
                    self.purchase_request_ids.ids,
                ),
                (
                    "purchase_document_type",
                    "=",
                    "rfq",
                ),
            ]
        )


        return {
            "type": "ir.actions.act_window",

            "name": _("RFQ"),

            "res_model": "purchase.order",

            "view_mode": "list,form",

            "domain": [
                (
                    "id",
                    "in",
                    rfqs.ids,
                )
            ],

            "target": "current",
        }



    # ==========================================================
    # OPEN PURCHASE ORDER SMART BUTTON
    # ==========================================================

    def action_open_purchase_orders(self):

        self.ensure_one()


        orders = self.env["purchase.order"].search(
            [
                (
                    "purchase_request_ids",
                    "in",
                    self.purchase_request_ids.ids,
                ),
                (
                    "purchase_document_type",
                    "=",
                    "po",
                ),
            ]
        )


        return {
            "type": "ir.actions.act_window",

            "name": _("Purchase Orders"),

            "res_model": "purchase.order",

            "view_mode": "list,form",

            "domain": [
                (
                    "id",
                    "in",
                    orders.ids,
                )
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

            "name": _("Source RFQ"),

            "res_model": "purchase.order",

            "view_mode": "form",

            "res_id": self.source_rfq_id.id,

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
            and not context.get("module_uninstall")
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

        # ======================================================
        # GENERATE RFQ / PO REFERENCE
        # ======================================================

        for vals in vals_list:

            document_type = vals.get(
                "purchase_document_type",
                "rfq"
            )

            if vals.get("name") in (
                False,
                "/",
                "New",
            ):

                if document_type == "rfq":

                    vals["name"] = (
                        self.env["ir.sequence"]
                        .next_by_code(
                            "purchase.order.rfq"
                        )
                        or _("New")
                    )

                elif document_type == "po":

                    vals["name"] = (
                        self.env["ir.sequence"]
                        .next_by_code(
                            "purchase.order.custom"
                        )
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

        if self.env.context.get("install_demo"):
            return super(
                PurchaseOrder,
                self
            ).button_confirm()

        # ==================================================
        # NORMAL PURCHASE ORDER CONFIRM
        # ==================================================

        if all(
            order.purchase_document_type == "po"
            for order in self
        ):

            for order in self:

                if not order.partner_id:

                    raise UserError(
                        _("Please select Vendor.")
                    )

                if order.approval_state != "approved":

                    raise UserError(
                        _(
                            "Purchase document must be approved before confirmation."
                        )
                    )

            return super(
                PurchaseOrder,
                self
            ).button_confirm()

        # ==================================================
        # RFQ -> CREATE PO
        # ==================================================

        for rfq in self:

            if not rfq.partner_id:

                raise UserError(
                    _(
                        "Please select Vendor before confirming RFQ."
                    )
                )

            if rfq.approval_state != "approved":

                raise UserError(
                    _(
                        "Purchase document must be approved before confirmation."
                    )
                )


            po = self.env["purchase.order"].with_context(
                from_purchase_request=True,
                skip_purchase_approval_workflow=True,
            ).create({

                "partner_id": rfq.partner_id.id,

                "origin": rfq.name,

                "source_rfq_id": rfq.id,

                "purchase_document_type": "po",

                "approval_stage": "po",

                "approval_state": "draft",

                "company_id": rfq.company_id.id,

                "purchase_request_ids":
                    [(6, 0, rfq.purchase_request_ids.ids)],

                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": line.product_id.id,

                            "name": line.name,

                            "product_qty": line.product_qty,

                            "product_uom_id": line.product_uom_id.id,

                            "date_planned": line.date_planned,

                            "purchase_request_line_id":
                                line.purchase_request_line_id.id,
                        }
                    )

                    for line in rfq.order_line
                ],
            })

            rfq.message_post(
                body=_(
                    "Purchase Order created: %s"
                )
                % po.name
            )


            return {
                "type": "ir.actions.act_window",

                "name": _("Purchase Order"),

                "res_model": "purchase.order",

                "res_id": po.id,

                "view_mode": "form",

                "target": "current",
            }
    
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