/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { PurchaseChart } from "./purchase_chart";


export class PurchaseReportingDashboard extends Component {

    static template = "pc_purchase_reporting_v19.PurchaseReportingDashboard";

    static components = {
        PurchaseChart,
    };


    setup() {

        this.action = useService("action");
        this.orm = useService("orm");


        this.state = useState({

            // KPI
            total_amount: 0,
            untaxed_amount: 0,
            order_count: 0,
            average_order: 0,

            // Chart data
            chart_labels: [],
            chart_values: [],

        });


        onWillStart(async () => {

            const data = await this.orm.call(
                "purchase.dashboard",
                "get_purchase_dashboard_data",
                []
            );


            // KPI data
            this.state.total_amount = data.total_amount;
            this.state.untaxed_amount = data.untaxed_amount;
            this.state.order_count = data.order_count;
            this.state.average_order = data.average_order;


            // Chart data
            this.state.chart_labels = data.chart_labels || [];
            this.state.chart_values = data.chart_values || [];


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