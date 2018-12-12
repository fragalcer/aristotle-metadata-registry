import axios from 'axios'
import { getCSRF } from '../lib/cookie.js'

export default {
    data: () => ({
        errors: {},
        loading: false,
        response: {}
    }),
    methods: {
        request: function(url, data, method) {
            let csrf_token = getCSRF()

            this.loading = true
            let promise = axios({
                method: method,
                url: url,
                data: data,
                headers: {'X-CSRFToken': csrf_token}
            })

            promise.then((response) => {
                this.response = response
                this.loading = false
            })

            promise.catch((error) => {
                if (error.response) {
                    // Server responded with non 2xx status
                    if (error.response.status == 400) {
                        this.errors = error.response.data
                    }
                    this.response = error.response
                } else if (error.request) {
                    // Request was sent, server did not respond
                    this.errors = {'request': ['Request could not be completed. Please try again soon']}
                } else {
                    // Request wasnt sent
                    this.errors = {'request': ['Request could not be completed']}
                }
                this.loading = false
            })
            // Return the promise so additional handlers can be added
            return promise
        },
        post: function(url, data) {
            return this.request(url, data, 'post')
        },
        get: function(url) {
            return this.request(url, {}, 'get')
        },
        patch: function(url, data) {
            return this.request(url, data, 'patch')
        },
        put: function(url, data) {
            return this.request(url, data, 'put')
        },
        delete: function(url, data) {
            return this.request(url, data, 'delete')
        },
        isEmpty: function(obj) {
            return (Object.keys(obj).length == 0)
        }
    },
    computed: {
        hasErrors: function() {
            return !this.isEmpty(this.errors)
        },
        hasResponse: function() {
            return !this.isEmpty(this.response)
        }
    }
}
