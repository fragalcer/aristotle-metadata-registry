<script>
import VueSimpleSuggest from 'vue-simple-suggest'

export default {
    extends: VueSimpleSuggest,
    methods: {
        // Replace setText, since we are using event to add a tag anyways
        // TODO Find a better long term solution to this
        setText: function() {
        }
    }
}
</script>
