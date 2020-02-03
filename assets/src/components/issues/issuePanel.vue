<template>
  <div class="issuePanel">
      <!-- Colapsable panel -->
      <collapse-panel :title="title" v-if="!hidePanel">
        <alert v-if="itemChanged" type="warning">
            {{ changedMessage }}
        </alert>
        <slot />
        <button v-if="canApprove" class="btn btn-success" @click="openConfirmDialog">
            Accept Changes & Close
        </button>
      </collapse-panel>
      <!-- Confirm modal -->
      <confirm-modal :visible="confirmOpen" :text="confirmMessage" @yes="approve" @no="closeConfirmDialog" />
  </div>
</template>

<script>
import { addHeaderMessage } from 'src/lib/messages.js'
import apiRequest from 'src/mixins/apiRequest.js'
import collapsePanel from '@/collapsePanel.vue'
import confirmModal from '@/yesNoModal.vue'
import Alert from 'uiv/src/components/alert/Alert.vue'

export default {
    mixins: [apiRequest],
    components: {
        'collapse-panel': collapsePanel,
        'confirm-modal': confirmModal,
        'alert': Alert
    },
    props: {
        fieldName: {
            type: String,
            required: true
        },
        canApprove: {
            type: Boolean,
            default: false
        },
        approveUrl: {
            type: String,
            required: true
        },
        itemChanged: {
            type: Boolean,
            default: false
        },
        hidePanel: {
            type: Boolean,
            default: false
        }
    },
    data: () => ({
        message: 'Changes applied',
        confirmMessage: 'Are you sure you want to accept these changes? Accepting changes will save a new version of the item with these changes applied.',
        changedMessage: 'The item has been changed since this issue was created',
        confirmOpen: false
    }),
    methods: {
        approve: function() {
            let data = {
                'isopen': false
            }

            let promise = this.post(this.approveUrl, data)
            promise.then((response) => {
                if (response.status == 200) {
                    addHeaderMessage(this.message)
                    this.$emit('set_open', false)
                }
            })
            this.confirmOpen = false
        },
        openConfirmDialog: function() {
            this.confirmOpen = true
        },
        closeConfirmDialog: function() {
            this.confirmOpen = false
        }
    },
    computed: {
        title: function() {
            return 'Proposed changes to ' + this.fieldName
        }
    }
}
</script>

<style>
a.blackLink {
    color: #333333;
}

.issuePanel button {
    margin-top: 10px;
}
</style>
