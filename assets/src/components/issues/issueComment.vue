<template>
    <div class="issueComment">
        <api-errors :errors="errors"></api-errors>
        <user-panel :pic="pic">
            <span slot="heading">
                New Comment
            </span>
            <textarea-resize
                class="form-control ta-fixed-width"
                v-model="body"
                :min-height="100"
                :max-height="200"
            />
            <div class="panel-footer text-right" slot="footer">
                <button v-if="canOpenClose" :class="openCloseClass" @click="openClose">{{ openCloseText }}</button>
                <button class="btn btn-primary" @click="makeComment">Comment</button>
            </div>
        </user-panel>
    </div>
</template>

<script>
import userPanel from '@/userPanel.vue'
import apiErrors from '@/apiErrorDisplay.vue'
import apiRequest from 'src/mixins/apiRequest.js'
import { VueTextareaAutosize } from 'vue-textarea-autosize'

export default {
    mixins: [apiRequest],
    props: {
        pic: {
            type: String,
            required: true
        },
        userId: {
            type: String,
            required: true
        },
        userName: {
            type: String,
            required: true
        },
        issueId: {
            type: String,
            required: true
        },
        isOpen: {
            type: Boolean,
            default: false
        },
        canOpenClose: {
            type: Boolean,
            default: false
        },
        commentUrl: {
            type: String,
            required: true
        },
        openCloseUrl: {
            type: String,
            required: true
        }
    },
    components: {
        'api-errors': apiErrors,
        'user-panel': userPanel,
        'textarea-resize': VueTextareaAutosize
    },
    data: () => ({
        body: '',
    }),
    created: function() {
        this.$emit('set_open', this.isOpen)
    },
    methods: {
        emitComment: function(data) {
            let newcomment = {
                'pic': this.pic,
                'name': this.userName,
                'created': data['created'],
                'body': data['body']
            }
            this.$emit('created', newcomment)
        },
        makeComment: function() {
            let data = {
                'body': this.body,
                'author': this.userId,
                'issue': this.issueId
            }

            let promise = this.post(this.commentUrl, data)
            promise.then((response) => {
                // If comment created
                if (response.status == 201) {
                    this.emitComment(response.data)
                    this.body = ''
                }
            })
        },
        openClose: function() {
            let data = {
                'isopen': !this.isOpen
            }

            if (this.body.length > 0) {
                data['comment'] = {
                    'body': this.body
                }
            }

            let promise = this.post(this.openCloseUrl, data)
            promise.then((response) => {
                // If success
                if (response.status == 200) {
                    if (response.data['comment'] != undefined) {
                        this.emitComment(response.data['comment'])
                    }
                    this.body = ''
                    this.$emit('set_open', response.data.issue.isopen)
                }
            })
        }
    },
    computed: {
        openCloseText: function() {
            let text
            if (this.isOpen) {
                text = 'Close'
            } else {
                text = 'Reopen'
            }

            if (this.body.length > 0) {
                text += ' and comment'
            } else {
                text += ' Issue'
            }
            return text
        },
        openCloseClass: function() {
            let base = 'btn btn-'
            if (this.isOpen) {
                return base + 'danger'
            } else {
                return base + 'success'
            }
        }
    }
}
</script>

<style>
.text-right {
    text-align: right;
}
</style>
