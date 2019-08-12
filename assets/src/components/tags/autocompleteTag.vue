<template>
  <vue-simple-suggest :list="getSuggestions" :filter-by-query="true" @select="makeSuggestion">
      <taggle-tags :tags="current_tags" :newtags="newTags" @tag-update="update_tags" />
  </vue-simple-suggest>
</template>

<script>
import VueSimpleSuggest from './mySimpleSuggest.vue'
import tagComponent from './tag.vue'

export default {
    components: {
        'taggle-tags': tagComponent,
        'vue-simple-suggest': VueSimpleSuggest
    },
    props: {
        'current_tags': {
            type: Array,
            required: true
        },
        'user_tags': {
            type: Array,
            required: true
        }
    },
    computed: {
        newTags: function() {
            let newTags = []
            for (let element of this.current_tags) {
                if (!this.user_tags.includes(element)) {
                    newTags.push(element)
                }
            }
            return newTags
        }
    },
    methods: {
        getSuggestions: function() {
            let suggestions = []
            for (let element of this.user_tags) {
                // Add to suggestions if not in current tags
                if (!this.current_tags.includes(element)) {
                    suggestions.push(element)
                }
            }
            return suggestions
        },
        makeSuggestion: function(suggestion) {
            if (suggestion != null) {
                this.current_tags.push(suggestion)
            }
        },
        update_tags: function(tags) {
            this.$emit('tag-update', tags)
        }
    }
}
</script>

<style>
.vue-simple-suggest.designed .suggestions {
  border-radius: 3px;
  border: 1px solid #aaa;
  background-color: #fff;
  opacity: 1;
  padding-left: 5px;
  padding-right: 5px;
}

.vue-simple-suggest.designed .suggestions .suggest-item {
  cursor: pointer;
  user-select: none;
  list-style-type: none;
}

.vue-simple-suggest.designed .suggestions .suggest-item,
.vue-simple-suggest.designed .suggestions .misc-item {
  padding: 5px 10px;
}

.vue-simple-suggest.designed .suggestions .suggest-item.hover {
  background-color: #2874D5 !important;
  color: #fff !important;
}

.vue-simple-suggest.designed .suggestions .suggest-item.selected {
  background-color: #2832D5;
  color: #fff;
}
</style>
