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
        // New document from a template file the suite ships or the user added.
        createFromTemplate: function (tpl) {
            once(() => window.sdk.command('create:new', JSON.stringify({template: {type: tpl.type, path: tpl.path}})));
        },
        // Native file picker for a template file (.dotx, .xltx, .potx, ...).
        browseTemplate: function (editor) {
            once(() => window.sdk.command('create:new', 'template:' + editor));
        },
        // Native file picker for any supported document.
        browseDocument: function () {
            once(() => window.sdk.command('open:folder', ''));
        },
    };

    // ----------------------------------------------------------------------
    // Template registry
    // Entries: {id, app, name, description, category, path, type, thumb}
    //   app       writer | sheet | presentation
    //   path      local template file
    //   type      file format code of the template (utils.defines.FileFormat)
    //   thumb     optional local image
    // Templates come from SOS.templates.register(), called by a bundled
    // manifest or by the shell; nothing is fetched from the network.
    // ----------------------------------------------------------------------

    const registry = [];
    SOS.templates = {
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

            window.CommonEvents && CommonEvents.fire('sos:templates', [registry.slice()]);
        },
        forApp: function (app) {
            app = app || SOS.currentApp();
            return registry.filter(t => app.isSuite() || t.app === app.id);
        },
        categories: function (app) {
            return this.forApp(app).reduce((out, t) => (out.indexOf(t.category) < 0 && out.push(t.category), out), []);
        },
    };

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
    // categories  show a category filter when templates have several
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
            run: () => SOS.actions.createFromTemplate(t),
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
    };

    SOS.TemplateGallery.prototype.cards = function () {
        const app = this.app;
        let cards = app.newTypes.map(t => blankCard(SOS.newTypes[t]));

        const category = this.withCategories ? this.store.get('gallery.category', 'all') : 'all';
        cards = cards.concat(SOS.templates.forApp(app)
                    .filter(t => category === 'all' || t.category === category)
                    .map(templateCard));

        if ( !app.isSuite() )
            cards = cards.concat(app.templateEditors.map(browseCard));

        return this.limit ? cards.slice(0, this.limit) : cards;
    };

    SOS.TemplateGallery.prototype.cardHtml = function (c) {
        const nt = c.kind === 'blank' && SOS.newTypes[c.key.split(':')[1]];
        let thumb;
        if ( c.thumb ) {
            thumb = `<img class="sos-card__img" src="${esc(c.thumb)}" alt="" onerror="this.parentNode.classList.add('sos-card__thumb--missing');this.remove()">`;
        } else if ( c.kind === 'browse' ) {
            thumb = `<svg class="sos-card__icon"><use href="#folder-big"></use></svg>`;
        } else {
            thumb = `<svg class="sos-card__icon"><use href="${nt ? nt.icon : '#template-item'}"></use></svg>`;
        }

        return `
            <div class="sos-card sos-card--${c.kind}" role="button" tabindex="0" data-key="${esc(c.key)}"
                    data-sos-app="${esc(c.app)}" title="${esc(c.name)}">
                <div class="sos-card__thumb">${thumb}</div>
                <div class="sos-card__name" ${c.langKey ? `l10n="${c.langKey}"` : ''}>${esc(c.name)}</div>
                <div class="sos-card__descr">${esc(c.description)}</div>
            </div>`;
    };

    SOS.TemplateGallery.prototype.render = function ($parent) {
        this.$el = $('<div class="sos-gallery"></div>').appendTo($parent);
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
        this._cards = this.cards();

        let chips = '';
        const cats = this.withCategories ? SOS.templates.categories(this.app) : [];
        if ( cats.length > 1 ) {
            const cur = this.store.get('gallery.category', 'all');
            chips = '<div class="sos-chips" role="toolbar">' +
                ['all'].concat(cats).map(c =>
                    `<button type="button" class="sos-chip ${c === cur ? 'sos-chip--active' : ''}" data-category="${esc(c)}"
                        aria-pressed="${c === cur}">${esc(c === 'all' ? text('sosAllTemplates', 'All') : c)}</button>`).join('') +
                '</div>';
        }

        this.$el.html(chips + '<div class="sos-gallery__grid">' + this._cards.map(c => this.cardHtml(c)).join('') + '</div>');
    };

    SOS.TemplateGallery.prototype.run = function (key) {
        const card = (this._cards || []).find(c => c.key === key);
        card && card.run();
    };
}();
