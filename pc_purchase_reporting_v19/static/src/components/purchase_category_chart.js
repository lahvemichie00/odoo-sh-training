/** @odoo-module **/

import { Component, onMounted, useRef } from "@odoo/owl";
import { loadJS } from "@web/core/assets";


export class PurchaseCategoryChart extends Component {


    static template = "pc_purchase_reporting_v19.PurchaseCategoryChart";



    setup() {

        this.chartRef = useRef("chart");



        onMounted(async () => {


            await loadJS(
                "/web/static/lib/Chart/Chart.js"
            );



            new Chart(

                this.chartRef.el,

                {

                    type: "pie",



                    data: {


                        labels: this.props.labels,



                        datasets: [

                            {

                                label: "Purchase Category",

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