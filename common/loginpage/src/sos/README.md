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

Template entries look like this:

```js
SOS.templates.register({
    app: 'writer',                 // writer | sheet | presentation
    name: 'Business letter',
    description: 'Formal letter with letterhead',
    category: 'business',
    path: '/opt/secure-office-suite/templates/writer/letter.dotx',
    type: 76,                      // utils.defines.FileFormat of the file
    thumb: 'templates/writer/letter.png',
});
```

## Settings store (`store.js`)

`SOS.store.scope(id)` gives a namespaced, JSON-valued key/value store on top of
the start page's local storage, which lives in the user profile and survives
upgrades. Bad values fall back to defaults; changes reach subscribers in every
window. Recent documents and pins stay in the desktop shell's own store.
