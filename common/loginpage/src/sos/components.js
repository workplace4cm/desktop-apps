/*
 * Secure Office Suite: shared start-page components
 *
 *   SOS.templates        local template registry (per application)
 *   SOS.AppHeader        brand, application name and greeting
 *   SOS.TemplateGallery  "New" cards: blank documents, templates, template files
 *   SOS.Section          titled block with optional actions
 *   SOS.actions          the desktop commands the components run
 *
 * Every component takes the identity to render for (SOS.currentApp() by
 * default), so one implementation serves the suite and all four applications.
 * Components only show commands the desktop shell can perform.
 */

+function () {
    'use strict';

    const SOS = window.SOS = window.SOS || {};

    const esc = function (s) {
        return String(s === undefined || s === null ? '' : s)
            .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
    };

    const text = function (key, fallback) {
        return (window.utils && utils.Lang && utils.Lang[key]) || fallback || key;
    };

    SOS.util = {esc: esc, text: text};

    // ----------------------------------------------------------------------
    // Desktop commands
    // ----------------------------------------------------------------------

    let lock = false;
    const once = function (fn) {
        // The shell opens a window per call; ignore double clicks.
        if ( lock ) return;
        lock = true;
        setTimeout(() => { lock = false; }, (window.utils && utils.defines && utils.defines.DBLCLICK_LOCK_TIMEOUT) || 1000);
        fn();
    };

    SOS.actions = {
        // Blank document: type is word, cell, slide or form.
        createBlank: function (type) {
            once(() => window.sdk.command('create:new', type));
        },
        // New document from a template of the library (installed or My
        // templates). The shell checks the file again and creates an
        // untitled document from a copy of it.
        createFromTemplate: function (tpl) {
            once(() => window.sdk.command('create:new',
                JSON.stringify({template: {id: tpl.id, app: tpl.app, type: tpl.type, path: tpl.path}})));
        },
        // My Templates in the user's Documents (created when missing).
        openTemplatesFolder: function () {
            window.sdk && sdk.command('sos:templates:folder', '{}');
        },
        // Native file picker for a template file (.dotx, .xltx, .potx, ...).
        browseTemplate: function (editor) {
            once(() => window.sdk.command('create:new', 'template:' + editor));
        },
        // Native file picker; an application's picker lists its own formats first.
        browseDocument: function () {
            once(() => openFile(OPEN_FILE_FOLDER, ''));
        },
    };

    // ----------------------------------------------------------------------
    // Template registry
    // Entries: {id, app, name, description, category, path, type, thumb,
    //           keywords, user}
    //   app       writer | sheet | presentation | pdf
    //   path      local template file
    //   type      file format code of the template (utils.defines.FileFormat)
    //   thumb     optional local image
    //   user      true for templates from the user's My Templates folder
    // Templates come from the installed manifest (converter/templates/sos/
    // manifest.js) and from the shell's scan of My Templates; nothing is
    // fetched from the network.
    //
    // The shell checks every file ("sos:templates:check"). Until it answers,
    // templates show; a template whose file is missing or damaged is then
    // left out of the gallery and listed in a notice instead, so every card
    // on screen opens a real document.
    // ----------------------------------------------------------------------

    const registry = [];
    const status = {};                  // id -> ok | missing | damaged | ...
    let userFolder = '';
    let checkTimer = 0;

    // file:///C:/a%20b/x.dotx -> C:/a b/x.dotx, file:///opt/x.dotx -> /opt/x.dotx
    const localPath = function (url) {
        const path = decodeURIComponent(url.pathname);
        return /^\/[A-Za-z]:\//.test(path) ? path.substring(1) : path;
    };

    const formatCode = function (f) {
        if ( typeof f === 'number' ) return f;
        const ff = window.utils && utils.defines && utils.defines.FileFormat;
        return ff && ff[f] || 0;
    };

    const userFormat = {
        dotx: 'FILE_DOCUMENT_DOTX', ott: 'FILE_DOCUMENT_OTT', dot: 'FILE_DOCUMENT_DOC',
        xltx: 'FILE_SPREADSHEET_XLTX', ots: 'FILE_SPREADSHEET_OTS', xlt: 'FILE_SPREADSHEET_XLS',
        potx: 'FILE_PRESENTATION_POTX', otp: 'FILE_PRESENTATION_OTP', pot: 'FILE_PRESENTATION_PPT',
    };

    const fire = function () {
        window.CommonEvents && CommonEvents.fire('sos:templates', [registry.slice()]);
    };

    const statusText = function (st) {
        const key = {missing: 'sosTplMissing', noaccess: 'sosTplNoAccess', empty: 'sosTplEmpty',
                     toolarge: 'sosTplTooLarge', damaged: 'sosTplDamaged', wrongtype: 'sosTplWrongType',
                     macros: 'sosTplMacros', outside: 'sosTplOutside'}[st] || 'sosTplDamaged';
        return text(key, st);
    };

    SOS.templates = {
        // Entries with file paths relative to base (a manifest's URL), as in
        // converter/templates/sos/manifest.js: a list, or {schema, templates}.
        registerFrom: function (base, list) {
            if ( !base ) return;
            if ( list && !Array.isArray(list) ) list = list.templates;
            this.register((list || []).map(t => {
                try {
                    const url = new URL(t.file, base);
                    return Object.assign({}, t, {
                        id: t.id || t.app + ':' + t.file,
                        path: localPath(url),
                        type: formatCode(t.type || t.format),
                        thumb: t.thumb ? new URL(t.thumb, base).href : undefined,
                    });
                } catch (e) {
                    console.warn('sos.templates: bad entry', t, e);
                }
            }).filter(t => !!t));
        },
        register: function (list) {
            (Array.isArray(list) ? list : [list]).forEach(t => {
                if ( !t || !t.path || !t.app || !SOS.apps[t.app] || SOS.apps[t.app].isSuite() ) {
                    console.warn('sos.templates: skipping invalid entry', t);
                    return;
                }

                const id = t.id || t.path;
                const i = registry.findIndex(r => r.id === id);
                const entry = Object.assign({category: 'general'}, t, {id: id});
                i < 0 ? registry.push(entry) : (registry[i] = entry);
            });

            fire();
            this.check();
        },
        // asks the shell to check the files and to list My Templates
        check: function () {
            if ( !(window.sdk && sdk.command) ) return;
            clearTimeout(checkTimer);
            checkTimer = setTimeout(() => {
                const items = registry.filter(t => !t.user).map(t => ({id: t.id, path: t.path, app: t.app}));
                sdk.command('sos:templates:check', JSON.stringify({items: items}));
            }, 0);
        },
        // the shell's answer: statuses and the templates of My Templates
        _applyStatus: function (data) {
            data = data || {};
            Object.assign(status, data.status || {});
            if ( data.userFolder ) userFolder = data.userFolder;

            if ( Array.isArray(data.user) ) {
                for ( let i = registry.length; i--; )
                    registry[i].user && registry.splice(i, 1);
                data.user.forEach(u => {
                    if ( !u || !u.path || !SOS.apps[u.app] ) return;
                    status[u.id] = u.status || 'ok';
                    registry.push({
                        id: u.id, app: u.app, user: true, name: u.name, path: u.path,
                        description: u.category ? text('sosMyTemplates', 'My templates') + ' · ' + u.category :
                                                  text('sosMyTemplates', 'My templates'),
                        category: text('sosMyTemplates', 'My templates'),
                        type: formatCode(userFormat[u.ext]),
                        thumb: u.thumb || undefined,
                        ext: u.ext,
                    });
                });
            }
            fire();
        },
        // a create request the shell refused
        _applyFailure: function (info) {
            if ( !info || !info.id ) return;
            status[info.id] = info.status || 'damaged';
            fire();
        },
        status: function (t) {
            return status[t.id] || 'unknown';
        },
        isUsable: function (t) {
            const st = status[t.id];
            return !st || st === 'ok';
        },
        // usable templates of the application
        forApp: function (app) {
            app = app || SOS.currentApp();
            return registry.filter(t => (app.isSuite() || t.app === app.id) && this.isUsable(t));
        },
        // templates of the application that are left out, with the reason
        unavailable: function (app) {
            app = app || SOS.currentApp();
            return registry.filter(t => (app.isSuite() || t.app === app.id) && !this.isUsable(t))
                           .map(t => ({template: t, status: status[t.id], reason: statusText(status[t.id])}));
        },
        categories: function (app) {
            const mine = text('sosMyTemplates', 'My templates');
            const cats = this.forApp(app).reduce((out, t) => (out.indexOf(t.category) < 0 && out.push(t.category), out), []);
            // My templates last
            return cats.filter(c => c !== mine).concat(cats.indexOf(mine) < 0 ? [] : [mine]);
        },
        matches: function (t, query) {
            const q = String(query || '').trim().toLowerCase();
            if ( !q ) return true;
            const hay = [t.name, t.description, t.category].concat(t.keywords || []).join(' ').toLowerCase();
            return q.split(/\s+/).every(w => hay.indexOf(w) >= 0);
        },
        userFolder: function () {
            return userFolder;
        },
        statusText: statusText,
    };

    if ( window.sdk && sdk.on ) {
        sdk.on('on_native_message', function (cmd, param) {
            if ( cmd === 'sos:templates:status' || cmd === 'sos:templates:failed' ) {
                let data;
                try { data = JSON.parse(param); } catch (e) { return; }
                cmd === 'sos:templates:status' ? SOS.templates._applyStatus(data) : SOS.templates._applyFailure(data);
            }
        });
        // templates added to My Templates while the app runs
        window.addEventListener('focus', () => SOS.templates.check());
    }

    // ----------------------------------------------------------------------
    // Application header
    // ----------------------------------------------------------------------

    const greeting = function (date) {
        const h = (date || new Date()).getHours();
        return h < 12 ? text('sosGoodMorning', 'Good morning') :
                h < 18 ? text('sosGoodAfternoon', 'Good afternoon') : text('sosGoodEvening', 'Good evening');
    };

    SOS.appBadge = function (app, cls) {
        app = app || SOS.currentApp();
        return app.isSuite() ?
            `<span class="sos-app-badge sos-app-badge--suite ${cls || ''}" aria-hidden="true">` +
                `<svg class="sos-app-badge__logo"><use href="#idx-logo-light-eo"></use></svg></span>` :
            `<span class="sos-app-badge ${cls || ''}" data-sos-app="${app.id}" aria-hidden="true">` +
                `${esc(app.id === 'pdf' ? 'PDF' : app.shortName.charAt(0))}</span>`;
    };

    SOS.AppHeader = function (opts) {
        this.app = (opts && opts.app) || SOS.currentApp();
    };

    SOS.AppHeader.prototype.render = function ($parent) {
        const app = this.app;
        this.$el = $(`
            <header class="sos-app-header">
                ${SOS.appBadge(app)}
                <div class="sos-app-header__titles">
                    <div class="sos-app-header__brand">${esc(SOS.apps.suite.name)}</div>
                    <h1 class="sos-app-header__name">${esc(app.isSuite() ? greeting() : app.name)}</h1>
                </div>
                <div class="sos-app-header__greeting">${esc(app.isSuite() ? '' : greeting())}</div>
            </header>`);
        $parent.append(this.$el);
        return this;
    };

    // ----------------------------------------------------------------------
    // Section: title, optional actions, body
    // ----------------------------------------------------------------------

    SOS.Section = function (opts) {
        this.opts = opts || {};
    };

    SOS.Section.prototype.render = function ($parent) {
        const o = this.opts;
        this.$el = $(`
            <section class="sos-section ${o.cls || ''}">
                <div class="sos-section__head">
                    <h2 class="sos-section__title" ${o.langKey ? `l10n="${o.langKey}"` : ''}>${esc(o.title)}</h2>
                    <div class="sos-section__actions"></div>
                </div>
                <div class="sos-section__body"></div>
            </section>`);
        (o.actions || []).forEach(a => {
            $(`<button type="button" class="sos-link-button" ${a.langKey ? `l10n="${a.langKey}"` : ''}>${esc(a.caption)}</button>`)
                .on('click', a.handler)
                .appendTo(this.$el.find('.sos-section__actions'));
        });
        $parent.append(this.$el);
        this.$body = this.$el.find('.sos-section__body');
        return this;
    };

    // ----------------------------------------------------------------------
    // Template gallery
    //   new SOS.TemplateGallery({app, limit, categories, store}).render($el)
    // limit       show at most this many cards (the Home strip); 0 = all
    // categories  the full gallery (New page): category filter, search,
    //             My templates, and a notice for templates left out
    // A template card opens a preview first (SOS.TemplatePreview); blank
    // documents and "Open PDF…" run at once.
    // ----------------------------------------------------------------------

    const blankCard = function (nt) {
        return {
            kind: 'blank',
            key: 'blank:' + nt.type,
            name: text(nt.langKey),
            langKey: nt.langKey,
            description: nt.format,
            app: nt.app,
            run: () => SOS.actions.createBlank(nt.type),
        };
    };

    const templateCard = function (t) {
        return {
            kind: 'template',
            key: 'tpl:' + t.id,
            name: t.name,
            description: t.description || '',
            category: t.category,
            thumb: t.thumb,
            app: t.app,
            template: t,
            run: () => SOS.actions.createFromTemplate(t),
        };
    };

    // EuroOffice PDF has no blank-document workflow of its own: opening a PDF
    // is its first action, so the gallery leads with it.
    const openCard = function (app) {
        return {
            kind: 'open',
            key: 'open:' + app.id,
            name: text('sosOpenPdf', 'Open PDF…'),
            langKey: 'sosOpenPdf',
            description: text('sosOpenPdfDescr', 'Browse this computer'),
            app: app.id,
            run: () => SOS.actions.browseDocument(),
        };
    };

    const browseCard = function (editor) {
        const app = Object.keys(SOS.newTypes).map(k => SOS.newTypes[k]).find(nt => nt.type === editor).app;
        return {
            kind: 'browse',
            key: 'browse:' + editor,
            name: text('sosTemplateFile', 'Template from file…'),
            langKey: 'sosTemplateFile',
            description: text('sosTemplateFileDescr', 'Pick a template on this computer'),
            app: app,
            run: () => SOS.actions.browseTemplate(editor),
        };
    };

    SOS.TemplateGallery = function (opts) {
        opts = opts || {};
        this.app = opts.app || SOS.currentApp();
        this.limit = opts.limit || 0;
        this.withCategories = !!opts.categories;
        this.store = opts.store || SOS.store.scope(this.app.id);
        this.query = '';
    };

    SOS.TemplateGallery.prototype.category = function () {
        if ( !this.withCategories ) return 'all';
        const cur = this.store.get('gallery.category', 'all');
        return cur === 'all' || SOS.templates.categories(this.app).indexOf(cur) >= 0 ? cur : 'all';
    };

    SOS.TemplateGallery.prototype.cards = function () {
        const app = this.app;
        const category = this.category();
        const searching = !!this.query.trim();
        let cards = [];

        if ( category === 'all' && !searching ) {
            cards = app.id === 'pdf' ? [openCard(app)] : [];
            cards = cards.concat(app.newTypes.map(t => blankCard(SOS.newTypes[t])));
        }

        cards = cards.concat(SOS.templates.forApp(app)
                    .filter(t => category === 'all' || t.category === category)
                    .filter(t => SOS.templates.matches(t, this.query))
                    .map(templateCard));

        if ( !app.isSuite() && category === 'all' && !searching )
            cards = cards.concat(app.templateEditors.map(browseCard));

        return this.limit ? cards.slice(0, this.limit) : cards;
    };

    SOS.TemplateGallery.prototype.cardHtml = function (c) {
        const nt = c.kind === 'blank' && SOS.newTypes[c.key.split(':')[1]];
        let thumb;
        if ( c.thumb ) {
            thumb = `<img class="sos-card__img" src="${esc(c.thumb)}" alt="" onerror="this.parentNode.classList.add('sos-card__thumb--missing');this.remove()">`;
        } else if ( c.kind === 'browse' || c.kind === 'open' ) {
            thumb = `<svg class="sos-card__icon"><use href="#folder-big"></use></svg>`;
        } else {
            const icon = nt ? nt.icon : (SOS.apps[c.app] ? '#' + SOS.apps[c.app].icon + '-big' : '#template-item');
            thumb = `<svg class="sos-card__icon"><use href="${icon}"></use></svg>`;
        }

        return `
            <div class="sos-card sos-card--${c.kind}" role="button" tabindex="0" data-key="${esc(c.key)}"
                    data-sos-app="${esc(c.app)}" title="${esc(c.name)}"
                    ${c.kind === 'template' ? 'aria-haspopup="dialog"' : ''}>
                <div class="sos-card__thumb">${thumb}</div>
                <div class="sos-card__name" ${c.langKey ? `l10n="${c.langKey}"` : ''}>${esc(c.name)}</div>
                <div class="sos-card__descr">${esc(c.description)}</div>
            </div>`;
    };

    SOS.TemplateGallery.prototype.render = function ($parent) {
        this.$el = $('<div class="sos-gallery"></div>').appendTo($parent);

        if ( this.withCategories ) {
            this.$tools = $(`
                <div class="sos-gallery__tools">
                    <input type="search" class="sos-search" spellcheck="false"
                           placeholder="${esc(text('sosSearchTemplates', 'Search templates'))}"
                           aria-label="${esc(text('sosSearchTemplates', 'Search templates'))}">
                    <button type="button" class="sos-link-button sos-gallery__folder">${esc(text('sosMyTemplatesFolder', 'Open My Templates folder'))}</button>
                </div>`).appendTo(this.$el);
            this.$tools.on('input', '.sos-search', e => {
                this.query = e.currentTarget.value;
                this.refresh();
            });
            this.$tools.on('keydown', '.sos-search', e => {
                if ( e.key === 'Escape' && this.query ) {
                    e.preventDefault();
                    e.currentTarget.value = this.query = '';
                    this.refresh();
                }
            });
            this.$tools.on('click', '.sos-gallery__folder', () => SOS.actions.openTemplatesFolder());
            this.$tools.find('.sos-gallery__folder').toggle(!this.app.isSuite() && this.app.templateEditors.length > 0);
        }
        this.$body = $('<div class="sos-gallery__body"></div>').appendTo(this.$el);
        this.refresh();

        this.$el.on('click', '.sos-card', e => this.run($(e.currentTarget).data('key')));
        this.$el.on('keydown', '.sos-card', e => {
            if ( e.key === 'Enter' || e.key === ' ' ) {
                e.preventDefault();
                this.run($(e.currentTarget).data('key'));
            } else if ( /^Arrow(Left|Right)$/.test(e.key) ) {
                const $cards = this.$el.find('.sos-card');
                const rtl = $('body').hasClass('rtl');
                const step = (e.key === 'ArrowRight') !== rtl ? 1 : -1;
                const i = $cards.index(e.currentTarget) + step;
                i >= 0 && i < $cards.length && $cards.eq(i).focus();
                e.preventDefault();
            }
        });
        this.$el.on('click', '.sos-chip', e => {
            this.store.set('gallery.category', $(e.currentTarget).data('category'));
            this.refresh();
        });

        window.CommonEvents && CommonEvents.on('sos:templates', () => this.refresh());
        return this;
    };

    SOS.TemplateGallery.prototype.refresh = function () {
        if ( !this.$body ) return;
        this._cards = this.cards();

        let chips = '';
        const cats = this.withCategories ? SOS.templates.categories(this.app) : [];
        if ( cats.length > 1 ) {
            const cur = this.category();
            chips = '<div class="sos-chips" role="toolbar">' +
                ['all'].concat(cats).map(c =>
                    `<button type="button" class="sos-chip ${c === cur ? 'sos-chip--active' : ''}" data-category="${esc(c)}"
                        aria-pressed="${c === cur}">${esc(c === 'all' ? text('sosAllTemplates', 'All') : c)}</button>`).join('') +
                '</div>';
        }

        let empty = '';
        if ( this.query.trim() && !this._cards.length )
            empty = `<p class="sos-gallery__empty">${esc(text('sosNoTemplatesFound', 'No templates match “%1”.').replace('%1', this.query.trim()))}</p>`;

        // templates left out because their files are missing or damaged
        let notice = '';
        if ( this.withCategories ) {
            const gone = SOS.templates.unavailable(this.app);
            if ( gone.length ) {
                notice = `<p class="sos-gallery__notice" role="status">${esc(text('sosTemplatesHidden',
                    'Some templates are not shown because their files are missing or damaged: %1.')
                    .replace('%1', gone.map(g => g.template.name + ' (' + g.reason + ')').join(', ')))}</p>`;
            }
        }

        this.$body.html(chips + '<div class="sos-gallery__grid">' + this._cards.map(c => this.cardHtml(c)).join('') + '</div>' +
                        empty + notice);
    };

    SOS.TemplateGallery.prototype.run = function (key, direct) {
        const cards = this._cards || [];
        const card = cards.find(c => c.key === key);
        if ( !card ) return;
        if ( card.kind !== 'template' || direct ) {
            card.run();
            return;
        }

        // preview, with the other templates of this view one arrow away
        const templates = cards.filter(c => c.kind === 'template').map(c => c.template);
        const $origin = this.$el.find(`.sos-card[data-key="${CSS.escape(key)}"]`);
        new SOS.TemplatePreview({
            templates: templates,
            index: templates.indexOf(card.template),
            onclose: () => $origin.length && $origin.focus(),
        }).show();
    };

    // ----------------------------------------------------------------------
    // Template preview
    //   new SOS.TemplatePreview({templates, index, onclose}).show()
    // Larger thumbnail, description, category and file type; Create makes
    // the document, arrows (or Left/Right) step through the templates.
    // ----------------------------------------------------------------------

    SOS.TemplatePreview = function (opts) {
        this.templates = opts.templates || [];
        this.index = Math.max(0, opts.index || 0);
        this.onclose = opts.onclose;
    };

    SOS.TemplatePreview.prototype.bodyHtml = function () {
        const t = this.templates[this.index];
        const app = SOS.apps[t.app];
        const ext = t.ext || (window.utils && utils.parseFileFormat ? utils.parseFileFormat(t.type) : '') ||
                    String(t.path).split('.').pop();
        const thumb = t.thumb ?
            `<img class="sos-preview__img" src="${esc(t.thumb)}" alt="" onerror="this.parentNode.classList.add('sos-preview__thumb--missing');this.remove()">` :
            `<svg class="sos-preview__icon"><use href="#${esc(app ? app.icon : 'template')}-big"></use></svg>`;
        const multi = this.templates.length > 1;
        return `
            <div class="sos-preview" data-sos-app="${esc(t.app)}">
                <button type="button" class="sos-preview__nav sos-preview__nav--prev" ${multi ? '' : 'hidden'}
                        aria-label="${esc(text('sosPrevTemplate', 'Previous template'))}">‹</button>
                <div class="sos-preview__thumb">${thumb}</div>
                <div class="sos-preview__info">
                    <h3 class="sos-preview__name">${esc(t.name)}</h3>
                    <p class="sos-preview__descr">${esc(t.description || '')}</p>
                    <dl class="sos-preview__meta">
                        <dt>${esc(text('sosTemplateCategory', 'Category'))}</dt><dd>${esc(t.category)}</dd>
                        <dt>${esc(text('sosTemplateFormat', 'Template file'))}</dt><dd>${esc(String(ext).toUpperCase())}</dd>
                    </dl>
                    <p class="sos-preview__hint">${esc(text('sosTemplateCreates', 'Creates a new %1 document. The template itself is not changed.')
                        .replace('%1', app ? app.name : ''))}</p>
                    <div class="sos-preview__actions">
                        <button type="button" class="btn btn--landing sos-preview__create">${esc(text('sosCreate', 'Create'))}</button>
                        <button type="button" class="btn sos-preview__cancel">${esc(text('sosCancel', 'Cancel'))}</button>
                    </div>
                    <div class="sos-preview__count">${multi ? esc(text('sosPreviewOf', 'Template %1 of %2')
                        .replace('%1', this.index + 1).replace('%2', this.templates.length)) : ''}</div>
                </div>
                <button type="button" class="sos-preview__nav sos-preview__nav--next" ${multi ? '' : 'hidden'}
                        aria-label="${esc(text('sosNextTemplate', 'Next template'))}">›</button>
            </div>`;
    };

    SOS.TemplatePreview.prototype.show = function () {
        if ( !this.templates.length ) return;
        const me = this;

        if ( window.Dialog ) {
            this.dlg = new Dialog({
                dialogClass: 'sos-dlg-preview',
                titleText: '',
                defaultWidth: 760,
                bodyTemplate: this.bodyHtml(),
                onclose: () => {
                    document.removeEventListener('keydown', me._onkey, true);
                    me.$el = null;
                    me.onclose && me.onclose();
                },
            });
            this.dlg.show();
            this.$el = this.dlg.getElements().$el;
        } else {
            // pages without the dialog kit (tests)
            this.$el = $(`<dialog class="dlg sos-dlg-preview"><div class="body">${this.bodyHtml()}</div></dialog>`).appendTo('body');
            this.$el.get(0).showModal && this.$el.get(0).showModal();
        }

        this.$el.on('click', '.sos-preview__create', () => me.create());
        this.$el.on('click', '.sos-preview__cancel', () => me.close());
        this.$el.on('click', '.sos-preview__nav--prev', () => me.step(-1));
        this.$el.on('click', '.sos-preview__nav--next', () => me.step(1));
        // keys work wherever the focus is while the preview is open
        this._onkey = e => {
            if ( !me.$el ) return;
            if ( /^Arrow(Left|Right)$/.test(e.key) && !$(e.target).is('input') ) {
                const rtl = $('body').hasClass('rtl');
                me.step((e.key === 'ArrowRight') !== rtl ? 1 : -1);
                e.preventDefault();
            } else if ( e.key === 'Enter' && !$(e.target).is('button') ) {
                me.create();
                e.preventDefault();
            }
        };
        document.addEventListener('keydown', this._onkey, true);
        setTimeout(() => me.$el && me.$el.find('.sos-preview__create').focus(), 0);
    };

    SOS.TemplatePreview.prototype.step = function (d) {
        const n = this.templates.length;
        if ( n < 2 ) return;
        this.index = (this.index + d + n) % n;
        this.$el.find('.body').html(this.bodyHtml());
        this.$el.find('.sos-preview__create').focus();
    };

    SOS.TemplatePreview.prototype.create = function () {
        const t = this.templates[this.index];
        this.close();
        SOS.actions.createFromTemplate(t);
    };

    SOS.TemplatePreview.prototype.close = function () {
        document.removeEventListener('keydown', this._onkey, true);
        if ( this.dlg ) this.dlg.close();
        else if ( this.$el ) { this.$el.remove(); this.onclose && this.onclose(); }
        this.$el = null;
    };
}();
