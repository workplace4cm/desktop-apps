/*
 * Secure Office Suite: recent documents
 *
 * Page side of the desktop shell's recent-document service
 * (win-linux/src/crecentdocuments.cpp). The shell keeps one list per
 * application in the user's profile folder and sends every list with
 * "sos:recents" whenever one changes; this module keeps the last copy and
 * turns the page's actions into shell commands. Entries are plain objects:
 *
 *   {path, name, ext, folder, app, pinned, origin, template,
 *    created, opened, saved, used, size, modified, status}
 *
 * status is "ok", "missing", "unreachable", "noaccess" or "unknown".
 *
 *   SOS.recents.list('writer')          pinned first, then most recently used
 *   SOS.recents.pin(entry, true)        also remove, clear, open, locate, explore
 *   CommonEvents.on('sos:recents', () => ...)            lists changed
 *   CommonEvents.on('sos:recents:missing', info => ...)  open found no file
 *
 * Removing an entry or clearing a list never touches the documents.
 */

+function () {
    'use strict';

    const SOS = window.SOS = window.SOS || {};
    const isWin = /Win/.test(navigator.platform);

    let lists = null;           // null until the shell has answered
    let engineList = [];        // the editor engine's own history: [{id, path}]

    const key = function (path) {
        const k = String(path || '').replace(/\\/g, '/');
        return isWin ? k.toLowerCase() : k;
    };

    const command = function (op, args) {
        window.sdk && sdk.command('sos:recents:' + op, JSON.stringify(args || {}));
    };

    const parse = function (param) {
        if ( typeof param !== 'string' ) return param;
        try { return JSON.parse(param); }
        catch (e) {
            try { return JSON.parse($('<div>').html(param).text()); }
            catch (e2) { console.warn('sos.recents: unreadable message'); }
        }
    };

    const appIds = function (app) {
        return !app || app === 'suite' ? Object.keys(lists || {}) : [app];
    };

    const byUse = function (a, b) {
        if ( !!a.pinned !== !!b.pinned ) return a.pinned ? -1 : 1;
        return a.used < b.used ? 1 : a.used > b.used ? -1 : 0;
    };

    // The engine keeps its own history (recents.xml), which the shell reads
    // as a record of what was opened. Forget a removed document there too,
    // highest id first so the ids still to come stay valid.
    const forgetInEngine = function (paths) {
        if ( !window.sdk || !sdk.LocalFileRemoveRecent ) return;

        const keys = paths.map(key);
        engineList.filter(e => keys.indexOf(key(e.path)) >= 0)
            .map(e => e.id)
            .sort((a, b) => b - a)
            .forEach(id => sdk.LocalFileRemoveRecent(id));
    };

    const recents = SOS.recents = {
        ready: function () {
            return lists !== null;
        },

        list: function (app) {
            let out = [];
            appIds(app).forEach(a => { out = out.concat(lists && lists[a] || []); });
            return out.sort(byUse);
        },

        refresh: function () {
            command('get');
        },

        check: function () {
            command('check');
        },

        open: function (entry) {
            command('open', {path: entry.path});
        },

        locate: function (entry) {
            command('locate', {path: entry.path});
        },

        explore: function (entry) {
            command('explore', {path: entry.path});
        },

        pin: function (entry, pinned) {
            command('pin', {path: entry.path, pinned: !!pinned});
        },

        remove: function (entry) {
            command('remove', {path: entry.path});
            forgetInEngine([entry.path]);
        },

        // clears the application's list; pinned documents stay unless asked
        clear: function (app, includePinned) {
            const gone = this.list(app).filter(e => includePinned || !e.pinned).map(e => e.path);
            command('clear', {app: app || 'suite', pinned: !!includePinned});
            forgetInEngine(gone);
        },

        // for tests and for pages without the shell
        _apply: function (data) {
            lists = data && data.lists || {};
            window.CommonEvents && CommonEvents.fire('sos:recents', [lists]);
        },

        key: key,
    };

    if ( window.sdk && sdk.on ) {
        sdk.on('on_native_message', function (cmd, param) {
            if ( cmd === 'sos:recents' ) {
                const data = parse(param);
                data && recents._apply(data);
            } else
            if ( cmd === 'sos:recents:missing' ) {
                const info = parse(param);
                info && window.CommonEvents && CommonEvents.fire('sos:recents:missing', [info]);
            }
        });

        sdk.on('onupdaterecents', function (arr) {
            engineList = (arr || []).map(e => ({id: e.id, path: $('<div>').html(e.path).text()}));
        });

        recents.refresh();
    }
}();
