import renderComponents from 'src/lib/renderComponents.js'
import { initCore } from 'src/lib/init.js'

import switchEdit from '@/switchEditApi.vue'
import inlineEdit from '@/inlineEdit.vue'

import 'src/styles/taggle.css'
import 'src/styles/aristotle.dashboard.less'

initCore()
renderComponents({
    'switch-edit': switchEdit,
    'inline-edit': inlineEdit
})
