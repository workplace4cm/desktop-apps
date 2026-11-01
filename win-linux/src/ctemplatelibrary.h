/*
 * Secure Office Suite: local template library
 *
 * The start pages show templates from two local places, never the network:
 *
 *  - the library installed with the application
 *    (<app>/converter/templates, listed by sos/manifest.js), and
 *  - "My templates", a folder in the user's Documents where people put
 *    their own .dotx, .xltx, .potx (and the OpenDocument or legacy binary
 *    equivalents). Each subfolder becomes a category; an image with the
 *    template's name (.png or .jpg) becomes its thumbnail.
 *
 * Before a start page shows a template, and again before a document is
 * created from it, the shell checks the file: it must exist, be readable,
 * be a complete package of the format its extension claims, belong to the
 * application, and carry no macros. A damaged or missing template is hidden
 * from the gallery and explained, never opened.
 *
 * Creating a document always starts from a copy of the template (the engine
 * converts it into a new, untitled document), so saving never writes to the
 * template. Only files inside the two library folders can be opened this
 * way; any other template goes through the file picker.
 *
 * Qt Core only, so it is unit-tested without the engine
 * (tests/templatelibrary).
 */

#ifndef CTEMPLATELIBRARY_H
#define CTEMPLATELIBRARY_H

#include <QString>
#include <QStringList>
#include <QJsonArray>
#include <QJsonObject>

class CTemplateLibrary
{
public:
    enum class Status {
        Ok,
        Missing,        // no such file
        NoAccess,       // can't be read
        Empty,          // zero bytes
        TooLarge,       // over maxBytes
        Damaged,        // truncated or not a valid package
        WrongType,      // not a template of this application
        Macros,         // macro-enabled: the suite doesn't run macros
    };

    static constexpr qint64 maxBytes = 50 * 1024 * 1024;
    static constexpr int maxUserTemplates = 300;

    // installed library and My templates; both are set by the shell at start
    static void setLibraryFolders(const QString& installed, const QString& user);
    static QString installedFolder();
    static QString userFolder();
    // My templates in the user's Documents
    static QString defaultUserFolder();
    // creates My templates with a short README when it doesn't exist yet
    static bool ensureUserFolder();

    // "writer", "sheet", "presentation", "pdf" or empty, from the extension
    static QString appForTemplate(const QString& path);
    static QStringList extensions(const QString& app);

    // full check of a template file; app empty = application of the extension
    static Status validate(const QString& path, const QString& app = QString());
    static QString statusName(Status s);
    static QString statusMessage(Status s, const QString& fileName);

    // a template the start pages may ask the shell to open: inside the
    // installed library or My templates (after resolving links)
    static bool isLibraryPath(const QString& path);

    // My templates: [{id, app, name, category, path, ext, thumb, status, user:true}]
    static QJsonArray scanUserFolder(const QString& folder = QString());

    // statuses of the page's templates: [{id, path, app}] -> {id: status}
    static QJsonObject check(const QJsonArray& items);

    // The installed library as sos/manifest.js lists it, for one application
    // (empty = all): [{id, app, name, description, category, path, thumb,
    // status}] with absolute paths and thumbnail file URLs. The editors'
    // File > New reads it through the shell, so they show the same
    // templates as the start pages without loading the manifest themselves.
    static QJsonArray installedTemplates(const QString& app = QString(), const QString& manifest = QString());
    // File > New of an editor: the application's usable templates, installed
    // ones first, then My templates. Damaged or missing files are left out.
    static QJsonArray templatesFor(const QString& app);

private:
    static Status validateZip(const QString& path, const QString& ext);
    static Status validateOle(const QString& path);
    static Status validatePdf(const QString& path);
};

#endif // CTEMPLATELIBRARY_H
