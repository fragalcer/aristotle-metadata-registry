var loading_notifications = false

function fetch_api_data(callback, num) {

    if (!loading_notifications) {
        loading_notifications = true;
        //suppressLoadingBlock = true
        var apiurl='/account/notifications/api/unread_list/'
        var full_url = apiurl + '?max=' + num

        setTimeout(function() {
            $.ajax({
                url: full_url, 
                dataType: "json",
                success: callback,
                complete: function() {
                    loading_notifications = false
                    //suppressLoadingBlock = false
                },
                error: function() {
                    display_notify_error()
                }
            })
        }, 500)
    }

}

// Callback for notify menu
function fill_aristotle_notification_menu(data) {
    update_notification_badge(data)
    var menu = $('.notify-menu').first()
    var notify_unread_url = '/account/notifications'
    if (menu) {
        menu.empty()
        if (data.unread_list.length > 0) {
            for (var i=0; i < data.unread_list.length; i++) {
                var item = data.unread_list[i];

                let text = item.verb+" - "+item.actor
                let element
                if (item.target_object_id) {
                    let target = '/notifyredirect/' + item.target_content_type + '/'
                    element = make_dropdown_item(text, target)
                } else {
                    element = make_dropdown_item(text)
                }
                menu.append(element)
            }

            let divider = document.createElement('li')
            divider.className = 'divider'
            menu.append(divider)

            var all_read_item = make_dropdown_item('Mark all as read', '#', 'fa fa-envelope fa-fw')
            all_read_item.id = 'notify_all_read'
            menu.append(all_read_item)
            $('#notify_all_read a').click(mark_all_unread)

            menu.append(make_dropdown_item('View all unread notifications', notify_unread_url, 'fa fa-inbox fa-fw'))
        } else {
            menu.append(make_dropdown_item('No unread notifications', notify_unread_url, 'fa fa-inbox fa-fw'))
        }
    }
}

function update_notification_badge(data) {
    var num_notifications = data.unread_count
    $('.notify-badge').each(function() {
        this.innerHTML = num_notifications
    })
}

function make_dropdown_item(text, href='#', icon=null) {
    var textelement = document.createElement('li')
    var linkelement = document.createElement('a')
    var textnode = document.createTextNode(text)
    linkelement.href = href

    if (icon != null) {
        let iconelement = document.createElement('i')
        iconelement.className = icon
        linkelement.appendChild(iconelement)
    }

    linkelement.appendChild(textnode)
    textelement.appendChild(linkelement)

    return textelement
}


function display_notify_error() {
    var menu = $('.notify-menu')[0]
    menu.innerHTML = ""

    // Add text
    let list_element = make_dropdown_item('Notifications could not be retrieved')

    menu.append(list_element)
}

function mark_all_unread() {
    var notify_mark_all_unread_url = '/account/notifications/api/mark-all-as-read/'

    $.getJSON(notify_mark_all_unread_url, function (data) {
        if (data.status == 'success') {
            reload_notifications()
        }
    })

}

export function reload_notifications() {
    if (!loading_notifications) {
        var menu = $('.notify-menu').first()
        menu.empty()

        // Make loading icon li element
        var listelement = document.createElement('li')
        var centerdiv = document.createElement('div')
        var icon = document.createElement('i')
        centerdiv.className = 'text-center'
        icon.className = 'fa fa-refresh fa-spin'
        centerdiv.appendChild(icon)
        listelement.appendChild(centerdiv)

        // Make text element
        var textelement = make_dropdown_item('Fetching Notifications...')

        menu.append(listelement)
        menu.append(textelement)

        // Perform update
        fetch_api_data(fill_aristotle_notification_menu, 5)
    }

}

export function initNotifications() {
    $('#header_menu_button_notifications').click(reload_notifications)
}
