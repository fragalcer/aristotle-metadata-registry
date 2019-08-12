<template>
    <div id="taggle-editor" class="input taggle_textarea" />
</template>

<script>
import Taggle from 'taggle'

export default {
    props: {
        /* List of tags currently applied */
        tags: {
            type: Array,
            required: true
        },
        /* List of tags that will be newly created (can be empty) */
        newtags: {
            type: Array,
            required: true
        },
        /* List of tags that are allowed (empty implies any are allowed) */
        allowedTags: {
            type: Array,
            default: () => []
        }
    },
    mounted: function() {
        this.tag_editor = new Taggle('taggle-editor', {
            tags: this.tags,
            preserveCase: true,
            clearOnBlur: false,
            allowDuplicates: false,
            onTagAdd: () => {
                this.updateTags()
            },
            onTagRemove: () => {
                this.updateTags()
            },
        })

        // Attach events, used by autocomplete
        let input = this.tag_editor.getInput()
        input.addEventListener('input', (e) => {
            this.$emit('input', e)
        })

        input.addEventListener('focus', (e) => {
            this.$emit('focus', e)
            this.$emit('input', input.value)
        })

        input.addEventListener('blur', (e) => {
            let rt = e.relatedTarget
            // If being blurred by tag submit button
            // TODO This is a quick fix, should be changed
            if (rt != null && rt.id == 'tag-editor-submit') {
                this.tag_editor.add(input.value)
            }
            // If related target not set or clicking on non button element
            if (rt == null || rt.tagName != 'BUTTON') {
                this.$emit('blur', e)
            }
        })

    },
    methods: {
        updateTags: function() {
            this.$emit('tag-update', this.tag_editor.getTagValues())
        }
    },
    watch: {
        tags: function() {
            let current_tags = this.tag_editor.getTagValues()
            for (let tag of this.tags) {
                // Add tag if not already present
                if (!current_tags.includes(tag)) {
                    this.tag_editor.add(tag)
                }
            }
        },
        newtags: function() {
            let elements = this.tag_editor.getTagElements()
            for (let element of elements) {
                let text = element.querySelector('.taggle_text').innerText
                if (this.newtags.includes(text)) {
                    element.classList.add('taggle_newtag')
                } else {
                    element.classList.remove('taggle_newtag')
                }
            }
        }
    }
}
</script>

<style>
@import '../../styles/taggle.css';
</style>
