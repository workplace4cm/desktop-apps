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
| `SOS.TemplateGallery` | Cards for blank documents, registered templates and "Template from file…"; category filter; arrow-key navigation |
| `SOS.templates` | Local template registry: `register()`, `forApp()`, `categories()` |
| `SOS.actions` | The desktop commands behind the components (`create:new`, `open:folder`) |

`panelnew.js` is the Backstage "New" page built from the gallery. The Home
page (`panelrecent.js`) uses the header, a gallery strip and the recent list,
which shows only the current application's formats.

## Templates

The galleries list local templates only. `common/templates/sos/manifest.js`
is installed as `converter/templates/sos/manifest.js` next to the start page,
which loads it with a plain `<script>` tag. It calls
`SOS.templates.registerFrom(document.currentScript.src, [...])` with paths
relative to itself:

```js
{app: 'writer', name: 'Business letter', description: 'Formal letter with letterhead',
 category: 'Business', file: 'writer/business-letter.dotx', format: 'FILE_DOCUMENT_DOTX',
 thumb: 'thumbs/writer-business-letter.png'}
```

A card runs `create:new {"template": {type, path}}`; the shell opens a new,
untitled document from a copy, so the template file never changes, and it
reports a missing or unreadable template instead of opening it. A thumbnail
that fails to load shows an empty frame.

The suite's own templates (Writer: letter, resume, report, meeting notes,
memo; Sheet: budget, calendar, invoice, financial report; Presentation:
business, project, education) and all thumbnails are built by
`tools/sos-templates/make_templates.py`. The other entries reuse templates
already shipped in `common/templates/EN`, and EuroOffice PDF lists the
fillable PDF forms from there.

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
window. Recent documents and pins stay in the desktop shell's own store.
