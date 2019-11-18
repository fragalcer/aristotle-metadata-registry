export function ajaxForm(selector='form.ajaxform') {

    $(selector).submit(function(e) {
        // Stop standard form submission
        e.preventDefault()

        var form = $(this)

        // Get form data
        var data = form.serialize()

        // Get form url
        var url = form.attr('action')
        if (url == undefined) {
            url = window.location.href
        }

        $.post(
            url,
            data,
            function(data) {
                // Delete any current messages
                $('.ajax-error').remove()
                $('.ajax-success').remove()

                if (data.success) {
                    if (data.redirect != undefined) {
                        window.location.assign(data.redirect)
                    } else {
                        var alert = $('<div>', {class: 'alert alert-success ajax-success', role: 'alert', text: data.message})
                        let container = $('.ajax-success-container').first()
                        if (container != undefined) {
                            container.append(alert)
                        } else {
                            form.prepend(alert)
                        }
                    }
                } else {
                    // Go through error keys
                    var keys = Object.keys(data.errors)
                    for (var i = 0; i < keys.length; i++) {
                        var key = keys[i]
                        // get error array
                        var errors = data.errors[key]

                        // Find matching field
                        var field = form.find('input[name=' + key + ']').first()
                        if (field.length == 0) {
                            // Try getting field-0 instead
                            field = form.find('input[name=' + key + '-0]').first()
                        }

                        // If field was found
                        if (field.length !=  0) {
                            let container = field.closest('.field-container')
                            var label = container.find('label').first()
                            var ul = $('<ul>', {class: 'alert alert-danger ajax-error'})
                            for (var j = 0; j < errors.length; j++) {
                                var li = $('<li>', {text: errors[j]})
                                ul.append(li)
                            }
                            ul.insertAfter(label)
                        }
                    }
                }
            }
        )

    })
}
