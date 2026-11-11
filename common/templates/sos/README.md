# Secure Office Suite template library

Everything here is installed with the application (`<app>/converter/templates/sos`)
and works without a network connection.

| Folder          | Contents                                                      |
|-----------------|---------------------------------------------------------------|
| `writer/`       | SecureOffice Writer templates (`.dotx`)                         |
| `sheet/`        | SecureOffice Sheet templates (`.xltx`)                          |
| `presentation/` | SecureOffice Presentation templates (`.potx`)                   |
| `thumbs/`       | 304×264 PNG previews for the gallery cards and preview dialog |
| `manifest.js`   | The list the start pages show (strict JSON between markers)   |

The PDF form templates and some Writer/Sheet/Presentation entries reuse the
files in `../EN`.

## How a template becomes a document

1. The start page shows the templates of its application (SecureOffice Writer,
   Sheet, Presentation or PDF). The desktop shell checks each file first
   (`win-linux/src/ctemplatelibrary.cpp`); a missing or damaged one is left
   out and named in a notice instead.
2. Clicking a card opens a preview (larger thumbnail, description, category,
   file type). **Create** (or Enter) asks the shell
   to create the document.
3. The shell checks the file again, then the engine converts a **copy** of it
   into a new, untitled document (`Document1.docx`, `Book1.xlsx`,
   `Presentation1.pptx`, a new PDF form) in the matching editor. Saving asks
   for a name and location; the template is never written to.
4. The new document joins the application's recent list when first saved.

## Adding templates to the installation

1. Put the file in `writer/`, `sheet/` or `presentation/` (OOXML template
   formats; no macro-enabled files, no links to external resources).
2. Add a 304×264 PNG to `thumbs/` (`tools/sos-templates/make_templates.py`
   renders them with LibreOffice).
3. Add an entry to `manifest.js`: `id` (`<app>.<name>`), `app`, `name`,
   `description`, `category`, `file`, `format`, `thumb`, optional `keywords`.
4. Run `python3 tools/sos-templates/verify_templates.py --manifest
   common/templates/sos/manifest.js`. CI runs the same check and, on the
   built package, opens, saves and reopens every template with the suite's
   own converter without network access.

## My templates (no change to the installation)

Each user has a **My Templates** folder in their Documents
(`Documents/Secure Office Suite/My Templates`; the New page has a link that
creates and opens it). Templates saved there appear under the *My templates*
category of their application:

- SecureOffice Writer: `.dotx`, `.ott`, `.dot`
- SecureOffice Sheet: `.xltx`, `.ots`, `.xlt`
- SecureOffice Presentation: `.potx`, `.otp`, `.pot`

A subfolder becomes a sub-category, and an image with the same name as the
template (`.png` or `.jpg`) is used as its preview. Macro-enabled templates
are not offered.

## PDF

SecureOffice PDF offers **Open PDF…**, a **Blank PDF form**, and the fillable
PDF form templates. Combining PDFs is done inside the PDF editor (copy pages
from one PDF in the page thumbnails and paste them into another); the engine
has no one-step "combine files" action, so the start page does not offer one.
