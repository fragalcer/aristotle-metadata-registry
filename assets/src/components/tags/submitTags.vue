<template>
    <div class="submit-tags">
      <saving v-if="loading"></saving>
      <button v-if="!loading" id="tag-editor-submit" type="button" class="btn btn-primary" @click="submit_tags">
          Save tags
      </button>
    </div>
</template>

<script>
import { addHeaderMessage } from 'src/lib/messages.js'
import apiRequest from 'src/mixins/apiRequest.js'
import saving from '@/saving.vue'

export default {
    props: {
        'submitUrl': {
            type: String,
            required: true
        },
        'tags': {
            type: Array,
            required: true
        }
    },
    mixins: [apiRequest],
    components: {
        'saving': saving
    },
    data: () => ({
        message: 'Tags Saved',
    }),
    methods: {
        submit_tags: function() {
            if (!this.loading) {
                var data = {
                    tags: this.tagsList,
                }

                this.put(this.submitUrl, data)
                .then((response) => {
                    addHeaderMessage(this.message)
                    this.$emit('tags-saved', response.data['tags'])
                })
            }
        }
    },
    watch: {
        errors: function(value) {
            this.$emit('errors', value)
        }
    },
    computed: {
        tagsList: function() {
            let list = []
            for (let tagname of this.tags) {
                list.push({name: tagname})
            }
            return list
        }
    }
}
</script>

<style>
.submit-tags {
    display: inline-block;
}
</style>
