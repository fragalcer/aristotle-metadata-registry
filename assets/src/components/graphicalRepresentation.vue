<template>
    <div>
        <template v-if="!ready">
            <i class="fa fa-spinner fa-pulse"></i> Please wait, we are preparing the graph.
        </template>
        <alert v-if="error" type="danger">There was an error with the graph. Please try again later</alert>
        <div :id="id" style="height: 400px; width: 100%; border-color: #d2d2d2; border-style: solid; border-width: thin">
        </div>
    </div>
</template>

<script>
    import { Alert } from 'uiv'
    import apiRequest from 'src/mixins/apiRequest.js'

    export default {
        data: () => ({
            ready: false,
            error: false,
            pollTime: 1000, // period to call checkStatus in ms
            timeout: 30000, // period after which failure assumed if still pending
            id: null,
            nodes: {},
            edges: {}
        }),
        mixins: [apiRequest],
        props: {
            url: String,
            typeOfGraph: String,
            direction: String,
            levelSeparation: String
        },
        components: {
            'alert': Alert
        },
        name: "graphicalRepresentation",
        mounted() {
            this.id = this._uid
            this.buildGraph()
        },
        methods: {
            buildGraph: function () {
                this.get(this.url).then((response) => {
                    let data = response.data
                    if (data.state !== 'PENDING') {
                        this.pending = false
                    }
                    if (data.is_ready) {
                        this.ready = true
                        // It is possible for the task to be done with state started for some reason
                        if (data.state !== 'SUCCESS' && data.state !== 'STARTED') {
                            this.error = true
                        } else if (data.result !== undefined) {
                            this.url = data.result
                        }
                        clearInterval(this.interval)
                    }


                    this.nodesProcessor(response.data.nodes)

                    this.edgesProcessor(response.data.edges)

                    import('vis').then((vis) => {

                        this.nodes = response.data.nodes
                        this.edges = response.data.edges

                        let nodes = new vis.DataSet(this.nodes);
                        let edges = new vis.DataSet(this.edges);

                        // create a network
                        let container = document.getElementById(String(this._uid));
                        let final_data = {
                            nodes: nodes,
                            edges: edges
                        };
                        let options = {
                            "clickToUse": true,
                            "nodes": {
                                "shape": 'box',
                                "borderWidth": 2,
                                "margin": 3,
                                "font": {
                                    // "face": "Courier",
                                    "size": 15
                                }
                            },
                            "edges": {
                                "chosen": false,
                            },
                            "interaction": {
                                "hover": true,
                                "tooltipDelay": 0,
                                "selectConnectedEdges": false
                            },
                            'layout': {
                                'hierarchical': {
                                    'enabled': true,
                                    'direction': this.direction,
                                    'sortMethod': 'directed',
                                    // 'sortMethod': 'hubsize',
                                    'levelSeparation': Number(this.levelSeparation)
                                }
                            }
                        };
                        let network = new vis.Network(container, final_data, options);

                        // // Make the vis.js canvas "active" as soon as the page is loaded:
                        // let canvas = document.getElementsByClassName('vis-network')[0]
                        // let overlay = document.getElementsByClassName('vis-overlay')[0]
                        //
                        // canvas.onmouseenter = function() {
                        //     canvas.classList.add("vis-active")
                        //     overlay.style.display = "none"
                        // }
                        //
                        // canvas.onmouseleave = function() {
                        //     canvas.classList.remove("vis-active")
                        //     overlay.style.display = "block"
                        // }

                        // Disable the physics as soon as the vis.js is loaded:
                        network.on("stabilizationIterationsDone", function () {
                            network.setOptions({physics: false})
                        })

                        network.on('hoverNode', function () {
                            document.body.style.cursor = 'pointer'

                        });

                        network.on('blurNode', function () {
                            document.body.style.cursor = 'default'
                        })


                        network.on('doubleClick', function (net) {
                            if (net.nodes.length > 0) {
                                let nodesArray = nodes.get(net.nodes)
                                let myNode = nodesArray[0]
                                window.location.href = myNode.absolute_url
                            }
                            if (net.edges.length > 0) {
                                let edgesArray = edges.get(net.edges)
                                let myEdge = edgesArray[0]
                                window.location.href = myEdge.absolute_url
                            }
                        })

                        if (this.typeOfGraph === "general") {
                            network.on('click', (net) => {
                                if (net.nodes.length > 0) {
                                    let nodesArray = nodes.get(net.nodes)
                                    let myNode = nodesArray[0]

                                    this.get(myNode.expand_node_get_url).then((response) => {

                                        this.nodesProcessor(response.data.nodes)

                                        for (let element of response.data.nodes) {
                                            let weAlreadyHaveNode = false
                                            for (let innerElement of this.nodes) {
                                                if (innerElement.id === element.id) {
                                                    weAlreadyHaveNode = true
                                                }
                                            }
                                            if (!weAlreadyHaveNode) {
                                                this.nodes.push(element)
                                            }
                                        }

                                        this.edgesProcessor(response.data.edges)

                                        console.log("THESE ARE THE EDGES:")
                                        console.log(response.data.edges)
                                        console.log("THESE ARE THE CURRENT EDGES:")
                                        console.log(this.edges)

                                        for (let element of response.data.edges) {
                                            let weAlreadyHaveEdge = false
                                            for (let innerElement of this.edges) {
                                                if (innerElement.from === element.from && innerElement.to === element.to) {
                                                    weAlreadyHaveEdge = true
                                                }
                                            }
                                            if (!weAlreadyHaveEdge) {
                                                this.edges.push(element)
                                            }
                                        }

                                        network.setData({nodes: new vis.DataSet(this.nodes), edges: new vis.DataSet(this.edges)})
                                        network.fit()
                                        network.stabiliz
                                    })
                                }
                            })
                        }

                        network.on('showPopup', function () {
                            document.body.style.cursor = 'pointer'
                        })

                        network.on('hidePopup', function () {
                            document.body.style.cursor = 'default'
                        })
                        this.ready = true
                    })
                })
                // Check for timeout if we are still pending
                if (this.pending) {
                    let time = Date.now()
                    if ((time - this.started) > this.timeout) {
                        this.ready = true
                        this.error = true
                        clearInterval(this.interval)
                    }
                }
            },
            sentenceTrimmer: function (sentence) {
                const maximumLength = 30
                let firstString
                let lastString = ""
                let indexOfSpace
                if (sentence.length <= maximumLength) { return sentence; }
                firstString = sentence.slice(0, maximumLength)
                indexOfSpace = Math.min(firstString.length, firstString.lastIndexOf(" "))

                if (sentence.length <= maximumLength * 2) {
                    firstString = firstString.substr(0, indexOfSpace) + "\n"
                    lastString = sentence.slice(indexOfSpace + 1, maximumLength * 2)
                    return firstString + lastString
                } else {
                    firstString = firstString.substr(0, indexOfSpace) + "\n"
                    let secondString = sentence.slice(indexOfSpace + 1, indexOfSpace + 1 + maximumLength)
                    let indexOfSpaceSecondString = Math.min(secondString.length, secondString.lastIndexOf(" "))
                    secondString = secondString.slice(0, indexOfSpaceSecondString) + "…\n"
                    lastString = sentence.slice(-maximumLength)
                    indexOfSpace = lastString.indexOf(" ")
                    lastString = "…" + lastString.slice(indexOfSpace + 1)
                    return firstString + secondString + lastString
                }

            },
            sentenceTrimmerSingleLine: function (sentence) {
                const maximumLength = 20
                if (sentence.length <= maximumLength) { return sentence; }
                return sentence.slice(0, maximumLength) + "…"
            },
            nodesProcessor: function (responseNodes) {
                for (let element of responseNodes) {
                        element.title = `<small>Name: ${element.name}</small><br>`
                        if (element.definition !== "") {
                            element.title = element.title.concat(`<small>Definition: ${element.short_definition}</small><br>`)
                        }
                        if (element.version !== "") {
                            element.title = element.title.concat(`<small>Version: ${element.version}</small>`)
                        }
                        if (this.typeOfGraph === "supersedes") {
                            element.label = this.sentenceTrimmer(element.name)
                        } else if (this.typeOfGraph === "general") {
                            element.label = this.sentenceTrimmer(element.name) + " \n(" + element.type + ")"
                        }

                        if (element.node_options) {
                            element.shape = element.node_options.shape
                            element.borderWidth = element.node_options.borderWidth
                            element.margin = element.node_options.margin
                            element["font"] = {}
                            element.font.size = element.node_options.font.size
                            element.color = '#ffc05d'
                        }
                    }
            },
            edgesProcessor: function (responseEdges) {

                let edges = []

                    for (let element of responseEdges) {

                        let roundness

                        if (this.typeOfGraph === "supersedes") {
                            element.label = this.sentenceTrimmerSingleLine(element.registration_authority)
                            element.title = `<small>Superseding registration authority: ${element.registration_authority}</small>`
                            element.from = element.older_item
                            element.to = element.newer_item
                            element.font = {align: "top", face: "Helvetica", color: "black"}
                            element.smooth = {"enabled": true, "type": "curvedCCW", "roundness": 0.2}
                            roundness = 0.35
                        } else if (this.typeOfGraph === "general") {
                            element.smooth = {"enabled": true, "type": "curvedCCW", "roundness": 0}
                            roundness = 0
                        }
                        element.arrows = "to"

                        // If the edge is "duplicated"
                        // (e.g. two or more edges have the same 'from' and 'to' values)
                        // Change the roundness of the curvature so they don't overlap:
                        for (let i = 0; i < edges.length; i++) {
                            // Comparing the "stringified" version of two object is the most performance efficient:
                            if (JSON.stringify(edges[i]) === JSON.stringify({"from": element.from, "to": element.to})) {
                                element.smooth = {"enabled": true, "type": "curvedCCW", "roundness": roundness}
                                roundness += 0.15
                            }
                        }
                        edges.push({"from": element.from, "to": element.to})
                    }

            },
        }
    }
</script>

<style scoped>

</style>
