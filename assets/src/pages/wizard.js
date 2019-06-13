// You're a wizard Harry
import init from 'src/lib/init.js'
import { initMoveable } from 'src/lib/moveable.js'

import settings from 'src/settings.json'
import 'src/styles/aristotle.wizard.less'

init()
initMoveable()

// So we can ignore warning when submitting a form
// Don't like using globals, but we need this state in unload handler
let formSubmitted = false

// Class to override the leaving behavior
let leaveLinks = document.querySelectorAll('.suppress-leave-warning');

for (let link of leaveLinks) {
    link.addEventListener('click', suppress_leave_warning)
}

// Suppress the prompt when the user navigates away from the page
function suppress_leave_warning() {
   window.removeEventListener('beforeunload', handleUnload)
}

// Display a prompt when the user navigates away from the page
function handleUnload(event) {
    if (!formSubmitted) {
        event.preventDefault()
        // Most newer browsers don't display this message and use a general message instead
        event.returnValue = 'Are you sure you want to leave?'
    }
}

if (settings.wizard_leave_prompt) {
    // add event
    window.addEventListener('beforeunload', handleUnload)

    // Set flag to false when submitting form
    let forms = document.querySelectorAll('form')
    for (let form of forms) {
        form.addEventListener('submit', () => {
            formSubmitted = true
        })
    }
}
