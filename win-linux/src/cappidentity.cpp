/*
 * Secure Office Suite: the four applications and their identities
 * (see cappidentity.h)
 */

#include "cappidentity.h"

#include <QDir>
#include <QFileInfo>
#include <QProcess>
#include <QUrl>

namespace {
    struct App {
        const char * id;
        const char * name;
        const char * shortName;
        const char * newKind;
        QStringList exts;
    };

    // keep in step with common/loginpage/src/sos/identity.js and the
    // file associations of the installers (package/inno, package/common/linux)
    const QList<App>& apps()
    {
        static const QList<App> list{
            {"writer", "EuroOffice Writer", "Writer", "word",
                {"doc", "docx", "docm", "dot", "dotx", "dotm", "odt", "ott", "fodt", "rtf", "txt",
                 "html", "htm", "mht", "mhtml", "epub", "fb2", "md", "xml", "pages", "hwp", "hwpx",
                 "wps", "wpt"}},
            {"sheet", "EuroOffice Sheet", "Sheet", "cell",
                {"xls", "xlsx", "xlsm", "xlsb", "xlt", "xltx", "xltm", "ods", "ots", "fods", "csv", "tsv",
                 "numbers", "et", "ett"}},
            {"presentation", "EuroOffice Presentation", "Presentation", "slide",
                {"ppt", "pptx", "pptm", "pps", "ppsx", "ppsm", "pot", "potx", "potm", "odp", "otp",
                 "fodp", "key", "odg", "dps", "dpt"}},
            {"pdf", "EuroOffice PDF", "PDF", "form",
                {"pdf", "djvu", "djv", "xps", "oxps", "docxf", "oform"}},
        };
        return list;
    }

    const App * find(const QString& id)
    {
        for (const App& a : apps()) {
            if ( id == QLatin1String(a.id) )
                return &a;
        }
        return nullptr;
    }

    const char * SUITE_NAME = "Secure Office Suite";

    QString g_current;

    QString capitalized(const QString& s)
    {
        return s.isEmpty() ? s : s.left(1).toUpper() + s.mid(1);
    }
}

QStringList AppIdentity::ids()
{
    QStringList out;
    for (const App& a : apps())
        out << a.id;
    return out;
}

bool AppIdentity::isApp(const QString& id)
{
    return find(id) != nullptr;
}

QString AppIdentity::current()
{
    return g_current;
}

void AppIdentity::setCurrent(const QString& id)
{
    g_current = isApp(id) ? id : QString();
}

QString AppIdentity::name(const QString& id)
{
    const App * a = find(id);
    return QString::fromUtf8(a ? a->name : SUITE_NAME);
}

QString AppIdentity::name()
{
    return name(g_current);
}

QString AppIdentity::shortName(const QString& id)
{
    const App * a = find(id);
    return QString::fromUtf8(a ? a->shortName : SUITE_NAME);
}

QString AppIdentity::windowTitle(const QString& document)
{
    return document.isEmpty() ? name() : document + " - " + name();
}

QString AppIdentity::appForExtension(const QString& ext)
{
    const QString e = ext.toLower();
    if ( !e.isEmpty() ) {
        for (const App& a : apps()) {
            if ( a.exts.contains(e) )
                return a.id;
        }
    }
    return QString();
}

QString AppIdentity::appForPath(const QString& path)
{
    return appForExtension(QFileInfo(path).suffix());
}

QString AppIdentity::appForNewKind(const QString& kind)
{
    for (const App& a : apps()) {
        if ( kind == QLatin1String(a.newKind) )
            return a.id;
    }
    return QString();
}

QStringList AppIdentity::extensions(const QString& id)
{
    const App * a = find(id);
    return a ? a->exts : QStringList();
}

QString AppIdentity::documentPath(const QString& arg, const QString& cwd)
{
    if ( arg.isEmpty() || arg.startsWith("--") )
        return QString();

    QString path = arg;
    if ( arg.startsWith("file://", Qt::CaseInsensitive) ) {
        path = QUrl(arg).toLocalFile();
    } else {
        // web addresses and app-scheme links are not local documents; a
        // Windows drive letter ("C:\...") is
        const int scheme = arg.indexOf(':');
        if ( scheme > 1 )
            return QString();
    }

    if ( path.isEmpty() )
        return QString();

    if ( QDir::isRelativePath(path) )
        path = QDir(cwd).absoluteFilePath(path);
    return QDir::cleanPath(path);
}

QString AppIdentity::appFromArgs(const QStringList& args)
{
    for (const QString& arg : args) {
        if ( arg.startsWith("--app=") ) {
            const QString id = arg.mid(6).toLower();
            if ( isApp(id) )
                return id;
        }
    }

    for (const QString& arg : args) {
        if ( arg.startsWith("--new:") ) {
            const QString id = appForNewKind(arg.mid(6));
            if ( !id.isEmpty() )
                return id;
        } else
        if ( !arg.startsWith("--") ) {
            const QString id = appForPath(documentPath(arg, QDir::currentPath()));
            if ( !id.isEmpty() )
                return id;
        }
    }
    return QString();
}

void AppIdentity::partitionArgs(const QString& app, const QStringList& args, const QString& cwd,
                                QStringList& keep, QMap<QString, QStringList>& routed)
{
    for (const QString& arg : args) {
        QString owner, forward = arg;
        if ( arg.startsWith("--new:") ) {
            owner = appForNewKind(arg.mid(6));
        } else {
            const QString path = documentPath(arg, cwd);
            if ( !path.isEmpty() ) {
                owner = appForPath(path);
                forward = QDir::toNativeSeparators(path);
            }
        }

        if ( !owner.isEmpty() && owner != app )
            routed[owner] << forward;
        else keep << arg;
    }
}

bool AppIdentity::hasDocumentArgs(const QStringList& args, const QString& cwd)
{
    for (const QString& arg : args) {
        if ( arg.startsWith("--new:") || !documentPath(arg, cwd).isEmpty() )
            return true;
    }
    return false;
}

QString AppIdentity::lockName(const QString& base)
{
    return g_current.isEmpty() ? base : base + "." + g_current;
}

QString AppIdentity::receiverClass(const QString& base)
{
    return g_current.isEmpty() ? base : base + capitalized(g_current);
}

int AppIdentity::instancePort(int basePort)
{
    const int i = ids().indexOf(g_current);
    return i < 0 ? basePort : basePort + 1 + i;
}

QString AppIdentity::userModelId(const QString& base)
{
    return g_current.isEmpty() ? base : base.section('.', 0, 0) + "." + capitalized(g_current);
}

QString AppIdentity::desktopFileName(const QString& base)
{
    return g_current.isEmpty() ? base : base + "-" + g_current;
}

QString AppIdentity::dataSuffix()
{
    return g_current.isEmpty() ? QString() : "-" + g_current;
}

QString AppIdentity::iconResource()
{
    return g_current.isEmpty() ? QString() : ":/sos/apps/" + g_current + ".svg";
}

bool AppIdentity::launch(const QString& program, const QString& app, const QStringList& args)
{
    if ( !isApp(app) || program.isEmpty() )
        return false;

    return QProcess::startDetached(program, QStringList{"--app=" + app} + args);
}
