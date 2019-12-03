/* globals CKEDITOR */
import 'ckeditor/ckeditor.js'
// This import is necessary to include, otherwise the import won't work
import 'ckeditor/plugins/justify/plugin.js'
import  {addPlugins} from 'src/lib/ckeditor_plugins.js'
addPlugins(CKEDITOR)

// Initialize a ckeditor instance config can be provided to function or in data-config attr
export function initCKEditor(config) {
    let textareas = document.querySelectorAll('textarea[data-type=ckeditortype]')
    for (let te of textareas) {
        initCKEditorFromTextarea(te, config)
    }
}

export function initCKEditorFromTextarea(textarea, config) {
    let editor = null
    let processed = textarea.getAttribute('data-processed')
    if (processed == 0 || processed == null) {
        // If config not provided use data-config
        if (config === undefined) {
            config = JSON.parse(textarea.getAttribute('data-config'));
        }
    config.specialChars = [
            '&euro;', '&lsquo;', '&rsquo;', '&ldquo;', '&rdquo;', '&ndash;', '&mdash;', '&iexcl;', '&cent;', '&pound;',
            '&curren;', '&yen;', '&brvbar;', '&sect;', '&uml;', '&copy;', '&ordf;', '&laquo;', '&not;', '&reg;', '&macr;',
            '&deg;', '&sup2;', '&sup3;', '&acute;', '&micro;', '&para;', '&middot;', '&cedil;', '&sup1;', '&ordm;', '&raquo;',
            '&frac14;', '&frac12;', '&frac34;', '&iquest;', '&Agrave;', '&Aacute;', '&Acirc;', '&Atilde;', '&Auml;',
            '&Aring;', '&AElig;', '&Ccedil;', '&Egrave;', '&Eacute;', '&Ecirc;', '&Euml;', '&Igrave;', '&Iacute;',
            '&Icirc;', '&Iuml;', '&ETH;', '&Ntilde;', '&Ograve;', '&Oacute;', '&Ocirc;', '&Otilde;', '&Ouml;', '&times;',
            '&Oslash;', '&Ugrave;', '&Uacute;', '&Ucirc;', '&Uuml;', '&Yacute;', '&THORN;', '&szlig;', '&agrave;', '&aacute;',
            '&acirc;', '&atilde;', '&auml;', '&aring;', '&aelig;', '&ccedil;', '&egrave;', '&eacute;', '&ecirc;', '&euml;',
            '&igrave;', '&iacute;', '&icirc;', '&iuml;', '&eth;', '&ntilde;', '&ograve;', '&oacute;', '&ocirc;', '&otilde;',
            '&ouml;', '&divide;', '&oslash;', '&ugrave;', '&uacute;', '&ucirc;', '&uuml;', '&yacute;', '&thorn;', '&yuml;',
            '&OElig;', '&oelig;', '&#372;', '&#374', '&#373', '&#375;', '&sbquo;', '&#8219;', '&bdquo;', '&hellip;', '&trade;',
            '&#9658;', '&bull;', '&rarr;', '&rArr;', '&hArr;', '&diams;', '&asymp;',
            '&cong;', '&asymp;', '&ne;', '&equiv;', '&le;', '&ge;',

//          [ '&psi;', 'psi' ],
        ];
        editor = CKEDITOR.replace(textarea, config)
        textarea.setAttribute('data-processed', 1)
    }
    return editor
}

// ReInitialize ckeditor instances
export function reinitCKEditors(form) {
    $(form).find('div.cke').remove()
    $(form).find('textarea[data-type=ckeditortype]').each(function() {
        let textarea = $(this)
        let config = JSON.parse(textarea.attr('data-config'));
        CKEDITOR.replace(this.id, config)
        textarea.attr('data-processed', 1)
    })

}
