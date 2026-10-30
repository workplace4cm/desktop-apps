/*
 * Secure Office Suite: local settings store
 *
 * Small key/value service on top of the start page's localStorage, which the
 * desktop shell keeps in the user's profile folder (not the install folder),
 * so values survive restarts and upgrades and need no network.
 *
 *  - Keys are namespaced: "sos:<scope>:<key>", where scope is "suite" for
 *    shared values or an application id for per-application values.
 *  - Values are JSON. A missing, unreadable or corrupt value returns the
 *    default instead of throwing, so a damaged entry can't break the page.
 *  - Every write goes through one setItem call, so a crash leaves either the
 *    old or the new value, never half of one.
 *  - Subscribers hear about changes made here and in other windows.
 *
 * Recent documents and their pins stay in the desktop shell's own store
 * (sdk.LocalFileRecents / recent:pinned); this service is for UI settings.
 *
 *   const store = SOS.store.scope(SOS.currentApp().id);
 *   store.get('gallery.category', 'all');
 *   store.set('gallery.category', 'business');
 */

+function () {
    'use strict';

    const SOS = window.SOS = window.SOS || {};
    const PREFIX = 'sos:';
    const SCHEMA_KEY = PREFIX + 'suite:schema';
    const SCHEMA_VERSION = 1;

    const backend = (function () {
        try {
            const s = window.localStorage, probe = PREFIX + 'probe';
            s.setItem(probe, '1');
            s.removeItem(probe);
            return s;
        } catch (e) {
            // No storage (private profile, locked file): keep values for this session only.
            const mem = {};
            return {
                getItem: k => mem.hasOwnProperty(k) ? mem[k] : null,
                setItem: (k, v) => { mem[k] = String(v); },
                removeItem: k => { delete mem[k]; },
                key: i => Object.keys(mem)[i] || null,
                get length() { return Object.keys(mem).length; },
            };
        }
    })();

    const listeners = [];
    const notify = function (fullkey, value) {
        listeners.slice().forEach(l => {
            if ( fullkey.indexOf(l.prefix) === 0 ) {
                try { l.fn(fullkey.substring(l.prefix.length), value); }
                catch (e) { console.error(e); }
            }
        });
    };

    const read = function (fullkey, def) {
        let raw;
        try { raw = backend.getItem(fullkey); } catch (e) { return def; }
        if ( raw === null || raw === undefined ) return def;

        try {
            const v = JSON.parse(raw);
            return v === null || v === undefined ? def : v;
        } catch (e) {
            console.warn('sos.store: dropping unreadable value', fullkey);
            try { backend.removeItem(fullkey); } catch (e2) {}
            return def;
        }
    };

    const write = function (fullkey, value) {
        try {
            if ( value === undefined ) backend.removeItem(fullkey);
            else backend.setItem(fullkey, JSON.stringify(value));
        } catch (e) {
            console.warn('sos.store: could not save', fullkey, e);
            return false;
        }

        notify(fullkey, value);
        return true;
    };

    const Scope = function (name) {
        this.name = String(name || 'suite');
        this.prefix = PREFIX + this.name + ':';
    };

    Scope.prototype.get = function (key, def) {
        return read(this.prefix + key, def);
    };

    Scope.prototype.set = function (key, value) {
        return write(this.prefix + key, value);
    };

    Scope.prototype.remove = function (key) {
        return write(this.prefix + key, undefined);
    };

    // Reads, changes and writes one value in a single step.
    Scope.prototype.update = function (key, fn, def) {
        return this.set(key, fn(this.get(key, def)));
    };

    Scope.prototype.keys = function () {
        const out = [];
        for ( let i = 0; i < backend.length; i++ ) {
            const k = backend.key(i);
            k && k.indexOf(this.prefix) === 0 && out.push(k.substring(this.prefix.length));
        }
        return out;
    };

    Scope.prototype.clear = function () {
        this.keys().forEach(k => this.remove(k));
    };

    // fn(key, value) runs after a change, here or in another window.
    Scope.prototype.subscribe = function (fn) {
        const l = {prefix: this.prefix, fn: fn};
        listeners.push(l);
        return () => { const i = listeners.indexOf(l); i >= 0 && listeners.splice(i, 1); };
    };

    window.addEventListener('storage', e => {
        if ( e.key && e.key.indexOf(PREFIX) === 0 ) {
            let v;
            try { v = e.newValue === null ? undefined : JSON.parse(e.newValue); } catch (err) {}
            notify(e.key, v);
        }
    });

    const scopes = {};
    SOS.store = {
        scope: function (name) {
            name = String(name || 'suite');
            return scopes[name] || (scopes[name] = new Scope(name));
        },
        suite: function () {
            return this.scope('suite');
        },
        schemaVersion: SCHEMA_VERSION,
    };

    // Future schema changes migrate here, keyed on the stored version.
    if ( read(SCHEMA_KEY, 0) < SCHEMA_VERSION )
        write(SCHEMA_KEY, SCHEMA_VERSION);
}();
