/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";


export class PurchaseReportingDashboard extends Component {

    static template = "pc_purchase_reporting_v19.PurchaseReportingDashboard";


    setup() {

        this.action = useService("action");
        this.orm = useService("orm");


        this.state = useState({
            total_amount: 0,
            untaxed_amount: 0,
            order_count: 0,
            average_order: 0,
        });


        onWillStart(async () => {

            const data = await this.orm.call(
                "purchase.dashboard",
                "get_purchase_dashboard_data",
                []
            );


            this.state.total_amount = data.total_amount;
            this.state.untaxed_amount = data.untaxed_amount;
            this.state.order_count = data.order_count;
            this.state.average_order = data.average_order;

        });

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