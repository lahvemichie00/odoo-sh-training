/** @odoo-module **/

import { Component, onMounted, useRef } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { loadJS } from "@web/core/assets";


export class PurchaseChart extends Component {

    static template = "pc_purchase_reporting_v19.PurchaseChart";


    setup() {

        this.chartRef = useRef("chart");


        onMounted(async () => {

            await loadJS(
                "/web/static/lib/Chart/Chart.js"
            );


            new Chart(
                this.chartRef.el,
                {

                    type: "line",


                    data: {

                        labels: this.props.labels,


                        datasets: [
                            {
                                label: "Purchase Amount",

                                data: this.props.values,
                            },
                        ],

                    },


                    options: {

                        responsive: true,

                    },

                }
            );

        });

    }

}


registry.category("components").add(
    "PurchaseChart",
    PurchaseChart
);