/*
 * Secure Office Suite: local template library (see ctemplatelibrary.h)
 */

#include "ctemplatelibrary.h"

#include <QCoreApplication>
#include <QDir>
#include <QDirIterator>
#include <QFile>
#include <QFileInfo>
#include <QHash>
#include <QStandardPaths>
#include <QUrl>
#include <QtEndian>

namespace {
    struct Kind {
        const char * app;
        enum { Ooxml, Odf, Ole, Pdf, Macro } container;
        const char * marker;        // OOXML main part or ODF mimetype
    };

    const QHash<QString, Kind>& kinds()
    {
        static const QHash<QString, Kind> k = {
            {"dotx", {"writer", Kind::Ooxml, "word/document.xml"}},
            {"ott",  {"writer", Kind::Odf, "application/vnd.oasis.opendocument.text-template"}},
            {"dot",  {"writer", Kind::Ole, nullptr}},
            {"dotm", {"writer", Kind::Macro, nullptr}},
            {"xltx", {"sheet", Kind::Ooxml, "xl/workbook.xml"}},
            {"ots",  {"sheet", Kind::Odf, "application/vnd.oasis.opendocument.spreadsheet-template"}},
            {"xlt",  {"sheet", Kind::Ole, nullptr}},
            {"xltm", {"sheet", Kind::Macro, nullptr}},
            {"potx", {"presentation", Kind::Ooxml, "ppt/presentation.xml"}},
            {"otp",  {"presentation", Kind::Odf, "application/vnd.oasis.opendocument.presentation-template"}},
            {"pot",  {"presentation", Kind::Ole, nullptr}},
            {"potm", {"presentation", Kind::Macro, nullptr}},
            {"pdf",  {"pdf", Kind::Pdf, nullptr}},
        };
        return k;
    }

    const QStringList ooxmlMainParts = {"word/document.xml", "xl/workbook.xml", "ppt/presentation.xml"};

    QString g_installed, g_user;

    quint16 u16(const QByteArray& b, int at) { return qFromLittleEndian<quint16>(b.constData() + at); }
    quint32 u32(const QByteArray& b, int at) { return qFromLittleEndian<quint32>(b.constData() + at); }

    QString canonical(const QString& path)
    {
        const QString c = QFileInfo(path).canonicalFilePath();
        return c.isEmpty() ? QDir::cleanPath(QFileInfo(path).absoluteFilePath()) : c;
    }

    bool isInside(const QString& path, const QString& folder)
    {
        if ( folder.isEmpty() )
            return false;
        const QString f = canonical(folder) + "/";
#ifdef Q_OS_WIN
        return canonical(path).startsWith(f, Qt::CaseInsensitive);
#else
        return canonical(path).startsWith(f);
#endif
    }
}

void CTemplateLibrary::setLibraryFolders(const QString& installed, const QString& user)
{
    g_installed = installed;
    g_user = user;
}

QString CTemplateLibrary::installedFolder()
{
    return g_installed;
}

QString CTemplateLibrary::userFolder()
{
    return g_user.isEmpty() ? defaultUserFolder() : g_user;
}

QString CTemplateLibrary::defaultUserFolder()
{
    QString docs = QStandardPaths::writableLocation(QStandardPaths::DocumentsLocation);
    if ( docs.isEmpty() )
        docs = QDir::homePath();
    return docs + "/Secure Office Suite/My Templates";
}

bool CTemplateLibrary::ensureUserFolder()
{
    const QString folder = userFolder();
    if ( QDir(folder).exists() )
        return true;
    if ( !QDir().mkpath(folder) )
        return false;

    QFile readme(folder + "/README.txt");
    if ( readme.open(QIODevice::WriteOnly | QIODevice::Text) ) {
        readme.write(
            "Secure Office Suite - My templates\n"
            "\n"
            "Templates saved in this folder appear on the start page of their application,\n"
            "under \"My templates\":\n"
            "  EuroOffice Writer        .dotx .ott .dot\n"
            "  EuroOffice Sheet         .xltx .ots .xlt\n"
            "  EuroOffice Presentation  .potx .otp .pot\n"
            "\n"
            "A subfolder becomes a category. A .png or .jpg with the same name as a\n"
            "template is shown as its preview. Macro-enabled templates (.dotm, .xltm,\n"
            ".potm) are not offered: the suite does not run macros.\n"
            "\n"
            "To make a template, create a document and use File > Save As with a\n"
            "template format (for example .dotx), saving it into this folder.\n"
            "A new document made from a template never changes the template.\n");
    }
    return true;
}

QString CTemplateLibrary::appForTemplate(const QString& path)
{
    const auto it = kinds().constFind(QFileInfo(path).suffix().toLower());
    return it == kinds().cend() ? QString() : QString::fromLatin1(it->app);
}

QStringList CTemplateLibrary::extensions(const QString& app)
{
    QStringList out;
    for (auto it = kinds().cbegin(); it != kinds().cend(); ++it) {
        if ( app == QLatin1String(it->app) && it->container != Kind::Macro )
            out << it.key();
    }
    out.sort();
    return out;
}

CTemplateLibrary::Status CTemplateLibrary::validate(const QString& path, const QString& app)
{
    const QFileInfo info(path);
    if ( path.isEmpty() || !info.exists() || !info.isFile() )
        return Status::Missing;
    if ( !info.isReadable() )
        return Status::NoAccess;

    const QString ext = info.suffix().toLower();
    const auto it = kinds().constFind(ext);
    if ( it == kinds().cend() )
        return Status::WrongType;
    if ( !app.isEmpty() && app != QLatin1String(it->app) )
        return Status::WrongType;
    if ( it->container == Kind::Macro )
        return Status::Macros;

    if ( info.size() == 0 )
        return Status::Empty;
    if ( info.size() > maxBytes )
        return Status::TooLarge;

    QFile f(path);
    if ( !f.open(QIODevice::ReadOnly) )
        return Status::NoAccess;
    f.close();

    switch ( it->container ) {
    case Kind::Ooxml:
    case Kind::Odf: return validateZip(path, ext);
    case Kind::Ole: return validateOle(path);
    case Kind::Pdf: return validatePdf(path);
    default: return Status::WrongType;
    }
}

CTemplateLibrary::Status CTemplateLibrary::validateZip(const QString& path, const QString& ext)
{
    const Kind kind = kinds().value(ext);
    QFile f(path);
    if ( !f.open(QIODevice::ReadOnly) )
        return Status::NoAccess;
    const qint64 size = f.size();
    if ( size < 22 )
        return Status::Damaged;

    if ( f.read(4) != QByteArray("PK\x03\x04", 4) )
        return Status::Damaged;

    // end of central directory: the last 22 bytes plus at most a 64 KB comment
    const qint64 tailLen = qMin<qint64>(size, 22 + 0xFFFF);
    f.seek(size - tailLen);
    const QByteArray tail = f.read(tailLen);
    const int eocd = tail.lastIndexOf(QByteArray("PK\x05\x06", 4));
    if ( eocd < 0 || eocd + 22 > tail.size() )
        return Status::Damaged;

    const qint64 eocdPos = size - tailLen + eocd;
    const quint16 count = u16(tail, eocd + 10);
    const quint32 cdSize = u32(tail, eocd + 12);
    const quint32 cdOffset = u32(tail, eocd + 16);
    if ( count == 0 || cdOffset == 0xFFFFFFFF || qint64(cdOffset) + cdSize > eocdPos )
        return Status::Damaged;

    f.seek(cdOffset);
    const QByteArray cd = f.read(cdSize);
    if ( cd.size() != int(cdSize) )
        return Status::Damaged;

    QStringList names;
    bool macros = false;
    qint64 mimetypeAt = -1;
    int pos = 0;
    for (int i = 0; i < count; ++i) {
        if ( pos + 46 > cd.size() || u32(cd, pos) != 0x02014b50 )
            return Status::Damaged;
        const quint32 compressed = u32(cd, pos + 20);
        const int nameLen = u16(cd, pos + 28);
        const int extraLen = u16(cd, pos + 30);
        const int commentLen = u16(cd, pos + 32);
        const quint32 local = u32(cd, pos + 42);
        if ( pos + 46 + nameLen > cd.size() )
            return Status::Damaged;
        const QString name = QString::fromUtf8(cd.mid(pos + 46, nameLen));

        // each entry's data must be there: a cut-off download fails here
        if ( qint64(local) + 30 + nameLen + compressed > cdOffset )
            return Status::Damaged;
        f.seek(local);
        if ( f.read(4) != QByteArray("PK\x03\x04", 4) )
            return Status::Damaged;

        names << name;
        const QString lower = name.toLower();
        if ( lower.endsWith("vbaproject.bin") || lower.endsWith("vbadata.xml") ||
                lower.startsWith("basic/") )
            macros = true;
        if ( name == "mimetype" )
            mimetypeAt = local;
        pos += 46 + nameLen + extraLen + commentLen;
    }

    if ( macros )
        return Status::Macros;

    if ( kind.container == Kind::Ooxml ) {
        if ( !names.contains("[Content_Types].xml") )
            return Status::Damaged;
        if ( !names.contains(QString::fromLatin1(kind.marker)) ) {
            for (const QString& other : ooxmlMainParts)
                if ( names.contains(other) )
                    return Status::WrongType;
            return Status::Damaged;
        }
        return Status::Ok;
    }

    // OpenDocument: an uncompressed "mimetype" entry names the kind
    if ( mimetypeAt < 0 || !names.contains("content.xml") )
        return Status::Damaged;
    f.seek(mimetypeAt);
    const QByteArray lh = f.read(30);
    if ( lh.size() != 30 || u16(lh, 8) != 0 )
        return Status::Damaged;
    const quint32 len = u32(lh, 18);
    f.seek(mimetypeAt + 30 + u16(lh, 26) + u16(lh, 28));
    const QByteArray mime = f.read(qMin<quint32>(len, 128)).trimmed();
    if ( mime == kind.marker )
        return Status::Ok;
    return mime.startsWith("application/vnd.oasis.opendocument.") ? Status::WrongType : Status::Damaged;
}

CTemplateLibrary::Status CTemplateLibrary::validateOle(const QString& path)
{
    QFile f(path);
    if ( !f.open(QIODevice::ReadOnly) )
        return Status::NoAccess;
    // compound file: signature, then at least the header and two sectors
    if ( f.read(8) != QByteArray("\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1", 8) )
        return Status::Damaged;
    return f.size() >= 1536 ? Status::Ok : Status::Damaged;
}

CTemplateLibrary::Status CTemplateLibrary::validatePdf(const QString& path)
{
    QFile f(path);
    if ( !f.open(QIODevice::ReadOnly) )
        return Status::NoAccess;
    const qint64 size = f.size();
    if ( size < 64 )
        return Status::Damaged;
    if ( !f.read(1024).contains("%PDF-") )
        return Status::Damaged;
    f.seek(qMax<qint64>(0, size - 2048));
    return f.read(2048).contains("%%EOF") ? Status::Ok : Status::Damaged;
}

QString CTemplateLibrary::statusName(Status s)
{
    switch ( s ) {
    case Status::Ok:        return "ok";
    case Status::Missing:   return "missing";
    case Status::NoAccess:  return "noaccess";
    case Status::Empty:     return "empty";
    case Status::TooLarge:  return "toolarge";
    case Status::Damaged:   return "damaged";
    case Status::WrongType: return "wrongtype";
    case Status::Macros:    return "macros";
    }
    return "damaged";
}

QString CTemplateLibrary::statusMessage(Status s, const QString& fileName)
{
    const char * ctx = "CTemplateLibrary";
    const QString n = fileName.toHtmlEscaped();
    switch ( s ) {
    case Status::Missing:
        return QCoreApplication::translate(ctx, "The template %1 is missing. It may have been moved or deleted.").arg(n);
    case Status::NoAccess:
        return QCoreApplication::translate(ctx, "The template %1 cannot be read. Check that you have permission to open it.").arg(n);
    case Status::Empty:
        return QCoreApplication::translate(ctx, "The template %1 is empty.").arg(n);
    case Status::TooLarge:
        return QCoreApplication::translate(ctx, "The template %1 is too large to be used as a template.").arg(n);
    case Status::WrongType:
        return QCoreApplication::translate(ctx, "The file %1 is not a template for this application.").arg(n);
    case Status::Macros:
        return QCoreApplication::translate(ctx, "The template %1 contains macros, which this suite does not run.").arg(n);
    case Status::Damaged:
        return QCoreApplication::translate(ctx, "The template %1 is damaged and cannot be used.").arg(n);
    case Status::Ok:
        break;
    }
    return QString();
}

bool CTemplateLibrary::isLibraryPath(const QString& path)
{
    return isInside(path, installedFolder()) || isInside(path, userFolder());
}

QJsonArray CTemplateLibrary::scanUserFolder(const QString& folderArg)
{
    const QString folder = folderArg.isEmpty() ? userFolder() : folderArg;
    QJsonArray out;
    QDir root(folder);
    if ( !root.exists() )
        return out;

    QDirIterator it(folder, QDir::Files | QDir::Readable | QDir::NoDotAndDotDot, QDirIterator::Subdirectories);
    QList<QJsonObject> found;
    while ( it.hasNext() && found.size() < maxUserTemplates ) {
        const QString path = it.next();
        const QFileInfo fi(path);
        const QString rel = root.relativeFilePath(path);
        const int depth = rel.count('/');
        const QString ext = fi.suffix().toLower();
        if ( depth > 1 || fi.fileName().startsWith('.') || fi.fileName().startsWith("~$") ||
                ext == "pdf" || !kinds().contains(ext) )
            continue;

        QString thumb;
        for (const char * img : {"png", "jpg", "jpeg"}) {
            const QString t = fi.absolutePath() + "/" + fi.completeBaseName() + "." + img;
            if ( QFileInfo::exists(t) ) {
                thumb = QUrl::fromLocalFile(t).toString();
                break;
            }
        }

        const Status st = validate(path);
        found << QJsonObject{
            {"id", "user:" + rel},
            {"app", appForTemplate(path)},
            {"name", fi.completeBaseName()},
            {"category", depth ? rel.section('/', 0, 0) : QString()},
            {"path", QDir::toNativeSeparators(path)},
            {"ext", ext},
            {"thumb", thumb},
            {"status", statusName(st)},
            {"user", true},
        };
    }

    std::sort(found.begin(), found.end(), [](const QJsonObject& a, const QJsonObject& b) {
        const QString ca = a["category"].toString(), cb = b["category"].toString();
        if ( ca != cb )
            return ca.isEmpty() || (!cb.isEmpty() && ca.localeAwareCompare(cb) < 0);
        return a["name"].toString().localeAwareCompare(b["name"].toString()) < 0;
    });
    for (const QJsonObject& o : found)
        out.append(o);
    return out;
}

QJsonObject CTemplateLibrary::check(const QJsonArray& items)
{
    QJsonObject out;
    for (const QJsonValue& v : items) {
        const QJsonObject o = v.toObject();
        const QString id = o["id"].toString(), path = o["path"].toString();
        if ( id.isEmpty() )
            continue;
        out[id] = isLibraryPath(path) ? statusName(validate(path, o["app"].toString())) : QString("outside");
    }
    return out;
}
