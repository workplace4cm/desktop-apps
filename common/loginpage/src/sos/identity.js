/*
 * Secure Office Suite: application identities
 *
 * One registry describes the suite and its four applications. Shared
 * components (start page header, template gallery, recent list, Backstage
 * navigation) read the current identity from here instead of hard-coding
 * an application, so the same code serves EuroOffice Writer, Sheet,
 * Presentation and PDF.
 *
 * The current application comes from the start page URL (?app=writer),
 * which the desktop shell sets from its --app=<id> command-line argument.
 * Without it the start page runs as the whole suite, as before.
 */

+function () {
    'use strict';

    const SOS = window.SOS = window.SOS || {};

    // Formats are the short names utils.parseFileFormat() returns.
    const apps = {
        suite: {
            id: 'suite',
            name: 'Secure Office Suite',
            shortName: 'Secure Office Suite',
            icon: 'suite',
            newTypes: ['word', 'cell', 'slide', 'form'],
            formats: null,              // every format
            templateEditors: ['word', 'cell', 'slide'],
        },
        writer: {
            id: 'writer',
            name: 'EuroOffice Writer',
            shortName: 'Writer',
            icon: 'docx',
            newTypes: ['word'],
            formats: ['doc', 'docx', 'docm', 'dotx', 'dotm', 'odt', 'ott', 'fodt', 'rtf', 'txt',
                      'html', 'mht', 'epub', 'fb2', 'xml', 'pages', 'hwp', 'hwpx'],
            templateEditors: ['word'],
        },
        sheet: {
            id: 'sheet',
            name: 'EuroOffice Sheet',
            shortName: 'Sheet',
            icon: 'xlsx',
            newTypes: ['cell'],
            formats: ['xls', 'xlsx', 'xlsm', 'xlsb', 'xltx', 'xltm', 'ods', 'ots', 'fods', 'csv', 'numbers'],
            templateEditors: ['cell'],
        },
        presentation: {
            id: 'presentation',
            name: 'EuroOffice Presentation',
            shortName: 'Presentation',
            icon: 'pptx',
            newTypes: ['slide'],
            formats: ['ppt', 'pptx', 'pptm', 'ppsx', 'ppsm', 'potx', 'potm', 'odp', 'otp', 'fodp', 'key', 'odg'],
            templateEditors: ['slide'],
        },
        pdf: {
            id: 'pdf',
            name: 'EuroOffice PDF',
            shortName: 'PDF',
            icon: 'pdf',
            newTypes: ['form'],
            formats: ['pdf', 'djvu', 'xps', 'oxps', 'docxf', 'oform'],
            templateEditors: [],
        },
    };

    // Blank-document kinds the desktop shell creates with "create:new <type>".
    const newTypes = {
        word:  {type: 'word',  app: 'writer',       format: 'DOCX', icon: '#docx-big', langKey: 'sosBlankDocument'},
        cell:  {type: 'cell',  app: 'sheet',        format: 'XLSX', icon: '#xlsx-big', langKey: 'sosBlankWorkbook'},
        slide: {type: 'slide', app: 'presentation', format: 'PPTX', icon: '#pptx-big', langKey: 'sosBlankPresentation'},
        form:  {type: 'form',  app: 'pdf',          format: 'PDF',  icon: '#pdf-big',  langKey: 'sosBlankForm'},
    };

    const Identity = function (app) {
        Object.assign(this, app);
    };

    Identity.prototype.isSuite = function () {
        return this.id === 'suite';
    };

    // True when a document of this format belongs to the application.
    Identity.prototype.accepts = function (format) {
        return !this.formats || this.formats.indexOf(String(format || '').toLowerCase()) >= 0;
    };

    // Application that owns a format, or undefined.
    const appForFormat = function (format) {
        const f = String(format || '').toLowerCase();
        for (const id in apps) {
            if (id !== 'suite' && apps[id].formats.indexOf(f) >= 0)
                return SOS.apps[id];
        }
    };

    const resolve = function (id) {
        id = String(id || '').toLowerCase();
        return apps.hasOwnProperty(id) ? id : 'suite';
    };

    SOS.apps = {};
    for (const id in apps)
        SOS.apps[id] = new Identity(apps[id]);

    SOS.newTypes = newTypes;
    SOS.appForFormat = appForFormat;

    let current = SOS.apps[resolve(window.utils && utils.inParams && utils.inParams.app)];
    SOS.currentApp = function () {
        return current;
    };

    // Marks the page with the identity; CSS (sos.less) does the rest.
    SOS.applyIdentity = function (root) {
        root = root || document.body;
        root.setAttribute('data-sos-app', current.id);
        document.title = current.name;
    };

    // For tests and for a future in-page application switch.
    SOS.setCurrentApp = function (id) {
        current = SOS.apps[resolve(id)];
        SOS.applyIdentity();
        window.CommonEvents && CommonEvents.fire('sos:app', [current]);
        return current;
    };
}();
