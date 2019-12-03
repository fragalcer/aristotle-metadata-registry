// Individual issue page
import { initCore } from 'src/lib/init.js'

import Vue from 'vue'
import rootComponent from '@/root/item_issues.js'


initCore();
new Vue(rootComponent);

for (let button of document.getElementsByClassName('swap-panels')) {
    button.addEventListener('click', () => {
        // Extract the data-target of which button was clicked
        let container = document.querySelector('.swap-container');
        let associatedElement = container.querySelector(event.target.dataset.target);

        // Add an active class to the clicked buttons
        for (let button of container.querySelectorAll('.swap-panels')) {
            if (event.target === button) {
                button.classList.add('active');
            }
            else {
                button.classList.remove('active');
            }
        }
        // Collapse all of them except the one that corresponds to the one that was clicked
        for (let collapsiblePanel of container.querySelectorAll('div.collapse')) {
            if (collapsiblePanel !== associatedElement) {
                collapsiblePanel.classList.remove('in');
            }
            else {
                collapsiblePanel.classList.add('in');
            }
        }
    });
}
