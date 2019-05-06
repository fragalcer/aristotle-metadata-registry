import {initCore} from 'src/lib/init.js'

import 'src/styles/taggle.css'
import 'src/styles/aristotle.dashboard.less'

initCore();

let selectAllCheckbox = document.getElementById('select-all-checkbox');
selectAllCheckbox.addEventListener("change", function () {
    toggle_all_checkboxes(this);
    show_select_all_div();
});

let selectAllQuerysetButton = document.getElementById("select-all-queryset")

selectAllQuerysetButton.addEventListener("click", function () {
    select_all_queryset()
});


function toggle_all_checkboxes(source) {
    var checkboxes = document.querySelectorAll('input[type="checkbox"]');
    for (var i = 0; i < checkboxes.length; i++) {
        if (checkboxes[i] != source) {
            checkboxes[i].checked = source.checked;
        }
    }
}

function show_select_all_div() {
    var select_all = document.getElementById('select-all-div')

    if (select_all.style.display == 'block') {
        select_all.style.display = 'none';
    } else {
        select_all.style.display = 'block';
    }

}

function select_all_queryset() {
    let length_queryset = document.getElementById('select-all-queryset').getAttribute('data-total-queryset');

    let markup = `All of your ${length_queryset} favourites
        have been selected. <button class="btn btn-outline btn-outline-info">Clear selections</button>
        `;
    document.getElementById("select-all-div").innerHTML = markup;
}
