# Secure Office Suite UI framework

Shared building blocks for the Office-style start pages of the suite and its
four applications: EuroOffice Writer, Sheet, Presentation and PDF.

## Identity

`identity.js` holds one registry, `SOS.apps`, with `suite`, `writer`, `sheet`,
`presentation` and `pdf`. Each entry has the display name, the blank-document
types it can create, the formats it owns and the template kinds it accepts.

The start page reads the current application from `?app=<id>`. The desktop
shell adds that parameter when it is started with `--app=<id>`. Without it the
page runs as the whole suite.

`SOS.applyIdentity()` writes `data-sos-app` on `<body>`. Styles only read the
`--sos-app-*` custom properties that follow from it, so a component never names
an application in its CSS.

## Design tokens

`tokens.less` defines the colours, type scale, spacing and breakpoints. The
editors use a byte-identical copy at
`web-apps/theme/secure-office-suite/assets/less/sos/tokens.less`, and the
DesktopEditors build fails if the two differ. Change both together.

## Components (`components.js`)

| Component | What it does |
|-----------|--------------|
| `SOS.AppHeader` | Brand line, application name and greeting |
| `SOS.Section` | Titled block with optional action buttons |
| `SOS.TemplateGallery` | Cards for blank documents, registered templates and "Template from file…"; category filter, search and My Templates link on the New page; arrow-key navigation |
| `SOS.TemplatePreview` | Preview dialog of a template: larger thumbnail, description, category, file type, **Create**; arrows step through the templates |
| `SOS.templates` | Local template registry: `register()`, `forApp()`, `categories()`, `unavailable()`; file checks and My Templates from the shell |
| `SOS.actions` | The desktop commands behind the components (`create:new`, `open:folder`) |

`panelnew.js` is the Backstage "New" page built from the gallery. The Home
page (`panelrecent.js`) uses the header, a gallery strip and the recent list,
which shows only the current application's documents.

## Templates

The galleries list local templates only: the library installed with the app
and the user's My Templates folder. See `common/templates/sos/README.md` for
the library, the manifest format and how to add templates.

- `converter/templates/sos/manifest.js` is loaded with a plain `<script>` tag
  and calls `SOS.templates.registerFrom(src, {schema: 1, templates: [...]})`.
- The page then sends `sos:templates:check {items: [{id, path, app}]}`. The
  shell answers `sos:templates:status {status: {id: ok|missing|damaged|...},
  user: [...], userFolder}`; `user` lists My Templates. Templates that are not
  `ok` are left out of the gallery and named in a notice on the New page. The
  check runs again when the window regains focus.
- A card opens `SOS.TemplatePreview`; **Create** (or Enter) runs `create:new {"template": {id, app, type, path}}`. The shell
  accepts only paths inside the template library, checks the file again and
  creates a new, untitled document from a copy. When the check fails it
  replies `sos:templates:failed {id, status}` and explains in a message.
- `sos:templates:folder` creates and opens My Templates.

## Open

`open:folder` takes `app:<id>` or `app:<id>|<folder>` from an application's
start page: the native picker then offers that application's formats first.
The recent list of an application shows and clears only its own documents.

## Launching

`--app=<id>` opens that application's start page. A second launch with
another `--app` while the suite runs switches the main window's start page
and brings it to the front; a launch with a document opens the document
without the start page. Home in an editor window returns to the start page
of that editor's application. The Windows Start Menu and the Linux menu have
one entry per application (`package/inno/common.iss`,
`package/common/linux/sos-app.desktop.m4`).

## Settings store (`store.js`)

`SOS.store.scope(id)` gives a namespaced, JSON-valued key/value store on top of
the start page's local storage, which lives in the user profile and survives
upgrades. Bad values fall back to defaults; changes reach subscribers in every
window. Recent documents have their own service (below).

## Recent documents (`recents.js`)

The desktop shell keeps the recent documents
(`win-linux/src/crecentdocuments.cpp`): one list per application in
`sos-recents.json`, in the user's profile folder next to the engine's
`recents.xml`. `recents.js` is the page side.

- Opened documents, the first save of a new or template-based document, every
  later save and every Save As are registered by the shell from the editors'
  document-name events. The engine's `recents.xml` is read at start and when
  it changes, so documents opened while no start page showed are not missed;
  its history (and pins) from earlier versions is imported once.
- An entry has `path, name, ext, folder, app, pinned, origin` (`opened`,
  `new`, `template`, `saveas`, `imported`), `template`, `created, opened,
  saved, used` (ISO UTC), `size, modified` (from the last check) and
  `status`: `ok`, `missing` (folder there, file not: moved, renamed or
  deleted), `unreachable` (folder or drive not there), `noaccess` or `unknown`.
  Files are checked off the UI thread.
- One path is one entry (compared case-insensitively on Windows). Each list
  keeps its pinned documents and the 50 most recently used others.
- Pin, unpin, remove and clear change the list only; a document is never
  touched. Removed or cleared entries leave a dated marker so the engine's
  list can't bring them back until the document is used again, and they are
  also removed from the engine's list.
- Opening a missing document offers **Find file…** (a picker in the nearest
  folder that still exists; the entry moves to the new place and keeps its
  pin) or **Remove from list**.
- The file is written atomically (temporary file, flushed, renamed); the
  previous session's copy is kept as `sos-recents.json.bak`. A damaged file is
  set aside as `.corrupt` and the backup, or else `recents.xml`, is loaded.
  Fields a version doesn't know are kept, so upgrades and downgrades share the
  file.

```js
SOS.recents.list('writer');                 // pinned first, then most recent
SOS.recents.pin(entry, true);               // also remove, clear(app, withPinned), open, locate, explore
CommonEvents.on('sos:recents', () => ...);  // lists changed
```

Commands to the shell are `sos:recents:get|check|pin|remove|clear|open|locate|explore`;
it answers with `sos:recents` (all lists) and `sos:recents:missing`. The
editors' File > Recent shows the same list for its application. Unit tests:
`win-linux/tests/recentdocuments`.
