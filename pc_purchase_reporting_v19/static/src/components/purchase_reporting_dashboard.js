/** @odoo-module **/

import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class PurchaseReportingDashboard extends Component {

    static template = "pc_purchase_reporting_v19.PurchaseReportingDashboard";

    setup() {
        this.action = useService("action");
    }


    openPurchaseAnalysis() {
        this.action.doAction(
            "pc_purchase_reporting_v19.action_purchase_analysis"
        );
    }


    openPurchaseOrderPeriod() {
        this.action.doAction(
            "pc_purchase_reporting_v19.action_purchase_order_period"
        );
    }


    openIncomingOrderPeriod() {
        this.action.doAction(
            "pc_purchase_reporting_v19.action_incoming_order_period"
        );
    }

}


registry.category("actions").add(
    "purchase_reporting_dashboard",
    PurchaseReportingDashboard
);