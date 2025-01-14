import { initCore } from 'src/lib/init.js'
import 'src/styles/aristotle.dashboard.less'
import renderComponents from 'src/lib/renderComponents.js'
import rulesEditor from '@/rules/rulesEditor.vue'

initCore()
renderComponents({
    'rules-editor': rulesEditor
})
