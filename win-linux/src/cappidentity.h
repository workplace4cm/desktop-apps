/*
 * Secure Office Suite: the four applications and their identities
 *
 * SecureOffice Writer, Sheet, Presentation and PDF are separate desktop
 * applications built from one program and one editing engine. Each runs in
 * its own process, started with --app=<id> (or by opening one of its
 * documents), and has its own:
 *
 *   - name, window title and icon;
 *   - single-instance lock: launching Writer again reaches the running
 *     Writer, never Sheet;
 *   - taskbar identity (Windows AppUserModelID, Linux desktop file and
 *     WM_CLASS), so its windows group under its own icon;
 *   - crash-recovery folder and browser profile;
 *   - start page, templates and recent documents (start page ?app=<id>).
 *
 * A process only hosts documents of its own application: anything else is
 * handed to the application it belongs to (route()). Without --app and
 * without documents the program shows the suite page, which only launches.
 *
 * Qt Core only, so it is unit tested (tests/appidentity).
 */

#ifndef CAPPIDENTITY_H
#define CAPPIDENTITY_H

#include <QString>
#include <QStringList>
#include <QMap>

namespace AppIdentity
{
    // "writer", "sheet", "presentation", "pdf"
    QStringList ids();
    bool isApp(const QString& id);

    // the application of this process; empty for the suite page
    QString current();
    void setCurrent(const QString& id);

    // "SecureOffice Writer"..., "Secure Office Suite" for an empty id
    QString name(const QString& id);
    QString name();

    // "Writer", "Sheet", "Presentation", "PDF"
    QString shortName(const QString& id);

    // window title: "Report.docx - SecureOffice Writer", or the name alone
    QString windowTitle(const QString& document = QString());

    // application of a file name extension, a path or a "--new:" kind
    // (word, cell, slide, form); empty when no application opens it
    QString appForExtension(const QString& ext);
    QString appForPath(const QString& path);
    QString appForNewKind(const QString& kind);
    QStringList extensions(const QString& id);

    // Command line. The application is --app=<id> when given, otherwise the
    // application of the first document (or --new: kind) on the line.
    QString appFromArgs(const QStringList& args);

    // A local document path from a command-line argument (plain path or
    // file:// URL), made absolute against cwd; empty for anything else.
    QString documentPath(const QString& arg, const QString& cwd);

    // Splits a command line between this application and the others:
    // documents and --new: kinds that belong to another application are
    // moved to `routed` (application -> its arguments); `keep` is the rest.
    // Documents whose application isn't known by extension stay.
    void partitionArgs(const QString& app, const QStringList& args, const QString& cwd,
                       QStringList& keep, QMap<QString, QStringList>& routed);

    // True when anything on the line is a document or a --new: kind.
    bool hasDocumentArgs(const QStringList& args, const QString& cwd);

    // Per-application keys, derived from the suite's own keys.
    QString lockName(const QString& base);          // "SecureOfficeSuite.Writer"
    QString receiverClass(const QString& base);     // message window class
    int     instancePort(int basePort);             // Linux single-instance port
    QString userModelId(const QString& base);       // Windows taskbar identity
    QString desktopFileName(const QString& base);   // Linux .desktop name (no suffix)
    QString dataSuffix();                           // "-writer", or empty
    QString iconResource();                         // ":/sos/apps/writer.svg"

    // Starts `app` with `args` (the documents for it). The new process hands
    // them to that application's running instance if there is one.
    bool launch(const QString& program, const QString& app, const QStringList& args);
}

#endif // CAPPIDENTITY_H
