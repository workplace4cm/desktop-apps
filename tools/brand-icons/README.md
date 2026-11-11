# Applying a Secure Office Suite icon pack

`apply_icons.py` puts an icon pack (the layout of
`secure-office-suite-installer-icons.zip`: `png/`, `windows/*.ico`,
`linux/hicolor/`) into desktop-apps and web-apps, in the same files the
earlier logos used:

| Where | Files |
|---|---|
| Installer (Inno) | `package/inno/res/WizImage-*`, `WizSmallImage-*` (icon swapped, "Secure Office Suite" text kept); `win-linux/extras/projicons/res/icons/desktopeditors.ico` (setup.exe) |
| Windows program | `win-linux/res/icons/desktopeditors-eo.ico` (DesktopEditors.exe, `{app}\app.ico` for Apps & features) |
| Top bar, splash | `win-linux/res/icons/logo-*-eo*`, `splash-eo.svg`, `app-icon-eo*.svg`, `app-icon_64.png` |
| Start page | `common/loginpage/res/img/idx-logo-*-eo.svg` (About, application badge) |
| Ubuntu | `package/common/linux/icons-eo/*.png` (suite icon) |
| Editors (web-apps) | `theme/secure-office-suite/assets/img/{about,embed,header}/*.svg` |

The four applications keep their own icons (`win-linux/res/icons/apps`,
`package/common/linux/icons-apps`, made by `tools/sos-apps/make_app_icons.py`).

    python3 -I apply_icons.py <unzipped pack> <folder holding desktop-apps and web-apps> <tmp>
    node render.js <tmp>/jobs.json      # top-bar PNGs, needs Playwright

The artwork is a raster image, so the SVGs embed it as a PNG.
