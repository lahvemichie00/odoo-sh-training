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