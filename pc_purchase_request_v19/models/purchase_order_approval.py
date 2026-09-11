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

    group_category_id = fields.Many2one(
        "product.group.category",
        string="Group Category",
        readonly=True,
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
        "order_line.purchase_request_line_id.purchase_request_id",
        "purchase_document_type",
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
        "order_line.purchase_request_line_id.purchase_request_id",
        "purchase_document_type",
    )

    def _compute_document_counts(self):

        for order in self:

            requests = (
                order.order_line
                .mapped("purchase_request_line_id")
                .mapped("purchase_request_id")
            )

            documents = self.env["purchase.order"].search(
                [
                    (
                        "order_line.purchase_request_line_id.purchase_request_id",
                        "in",
                        requests.ids,
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
                    "order_line.purchase_request_line_id.purchase_request_id",
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
                    "order_line.purchase_request_line_id.purchase_request_id",
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

            if not vals.get("name") or vals.get("name") in (
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


        for order in self:

            if order.purchase_document_type != "po":

                raise UserError(
                    _(
                        "Only Purchase Order can be confirmed."
                    )
                )


            if not order.partner_id:

                raise UserError(
                    _(
                        "Please select Vendor."
                    )
                )


            if order.approval_state != "approved":

                raise UserError(
                    _(
                        "Purchase Order must be approved before confirmation."
                    )
                )


        return super(
            PurchaseOrder,
            self
        ).button_confirm()

    # ==========================================================
    # CREATE PO FROM APPROVED RFQ
    # ==========================================================

    def action_create_po_from_rfq(self):

        self.ensure_one()

        if self.purchase_document_type != "rfq":
            raise UserError(
                _("Only RFQ can create Purchase Order.")
            )

        if self.approval_state != "approved":
            raise UserError(
                _("RFQ must be approved before creating PO.")
            )


        po = self.env["purchase.order"].with_context(
            from_purchase_request=True,
            skip_purchase_approval_workflow=True,
        ).create({

            "partner_id": self.partner_id.id,

            "origin": self.name,

            "source_rfq_id": self.id,

            "purchase_document_type": "po",

            "approval_stage": "po",

            "approval_state": "draft",

            "company_id": self.company_id.id,

            "order_line": [
                (
                    0,
                    0,
                    {
                        "product_id": line.product_id.id,

                        "name": line.name,

                        "product_qty": line.product_qty,

                        "product_uom_id": line.product_uom_id.id,

                        "price_unit": line.price_unit,

                        "taxes_id": [
                            (6, 0, line.taxes_id.ids)
                        ],

                        "date_planned": line.date_planned,

                        "purchase_request_line_id":
                            line.purchase_request_line_id.id,
                    }
                )

                for line in self.order_line
            ],
        })


        self.message_post(
            body=_(
                "Purchase Order created: %s"
            ) % po.name
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
    # OPEN FOC WIZARD
    # ==========================================================

    def action_add_foc_line(self):

        self.ensure_one()


        return {
            "type": "ir.actions.act_window",

            "name": _("Add FOC Product"),

            "res_model": "purchase.order.foc.wizard",

            "view_mode": "form",

            "target": "new",

            "context": {

                "default_purchase_order_id":
                    self.id,

            },

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

    def _compute_receipt_count(self):
        for order in self:
            order.receipt_count = 0


    def _compute_invoice_count(self):
        for order in self:
            order.invoice_count = 0


class PurchaseOrderLine(models.Model):

    _inherit = "purchase.order.line"


    is_foc = fields.Boolean(
        string="FOC",
        default=False,
    )