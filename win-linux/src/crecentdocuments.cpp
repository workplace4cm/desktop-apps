/*
 * Secure Office Suite: recent documents (see crecentdocuments.h)
 */

#include "crecentdocuments.h"
#include "cappidentity.h"

#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QSaveFile>
#include <QLockFile>
#include <QScopedPointer>
#include <QJsonDocument>
#include <QJsonValue>
#include <QFileSystemWatcher>
#include <QTimer>
#include <QThread>
#include <QXmlStreamReader>
#include <QDebug>
#include <algorithm>

#ifdef Q_OS_WIN
# ifndef NOMINMAX
#  define NOMINMAX
# endif
# include <windows.h>
# include <io.h>
#else
# include <unistd.h>
#endif

namespace {
    const char * STORE_NAME = "sos-recents.json";
    const char * NATIVE_NAME = "recents.xml";
    const int MAX_TOMBSTONES = 1000;
    const int DUPLICATE_EVENT_MS = 3000;
    const int LOCK_WAIT_MS = 3000;

    bool isRemote(const QString& path)
    {
        const int i = path.indexOf("://");
        return i > 1 && !path.startsWith("file://", Qt::CaseInsensitive);
    }

    QString displayPath(const QString& path)
    {
        return QDir::toNativeSeparators(QDir::cleanPath(QDir::fromNativeSeparators(path)));
    }

    bool syncToDisk(QSaveFile& f)
    {
        if ( !f.flush() ) return false;
#ifdef Q_OS_WIN
        HANDLE h = reinterpret_cast<HANDLE>(_get_osfhandle(f.handle()));
        return h == INVALID_HANDLE_VALUE || FlushFileBuffers(h);
#else
        return ::fsync(f.handle()) == 0;
#endif
    }
}

CRecentDocuments& CRecentDocuments::instance()
{
    // never destroyed: a file check may still be running when the app quits
    static CRecentDocuments * _instance = new CRecentDocuments;
    return *_instance;
}

CRecentDocuments::CRecentDocuments(QObject * parent)
    : QObject(parent)
{
}

CRecentDocuments::~CRecentDocuments()
{
    if ( m_checker ) {
        m_checker->disconnect(this);
        m_checker->wait();
    }
}

/* several applications share the store */

// The four applications run as separate processes and share one store.
// Every change happens inside a transaction: take the store's lock file,
// read what another application may have written since, change, save.
CRecentDocuments::Transaction::Transaction(CRecentDocuments * store) :
    m_store(store)
{
    if ( m_store->m_depth++ == 0 && !m_store->m_file.isEmpty() ) {
        QDir().mkpath(m_store->m_dataDir);
        m_lock = new QLockFile(m_store->m_file + ".lock");
        m_lock->setStaleLockTime(10000);
        if ( !m_lock->tryLock(LOCK_WAIT_MS) )
            qWarning() << "recent documents: store is busy, changing it anyway";
        m_store->syncFromDisk();
    }
}

CRecentDocuments::Transaction::~Transaction()
{
    if ( --m_store->m_depth == 0 && m_lock ) {
        m_lock->unlock();
        delete m_lock;
    }
}

QPair<qint64, qint64> CRecentDocuments::diskStamp() const
{
    QFileInfo fi(m_file);
    fi.refresh();
    return fi.exists() ? qMakePair(fi.lastModified().toMSecsSinceEpoch(), fi.size()) : qMakePair(qint64(-1), qint64(-1));
}

bool CRecentDocuments::syncFromDisk()
{
    if ( m_file.isEmpty() || diskStamp() == m_stamp )
        return false;

    // another application saved: take its version (a damaged file is
    // ignored here; load() deals with it at the next start)
    const QJsonObject mine = m_root;
    if ( !loadFile(m_file) ) {
        m_root = mine;
        return false;
    }
    if ( !m_root.value("lists").isObject() )
        m_root["lists"] = QJsonObject();
    m_stamp = diskStamp();
    m_external = true;
    return true;
}

void CRecentDocuments::init(const QString& dataDir, bool watchNative)
{
    m_dataDir = QDir::cleanPath(dataDir);
    m_file = m_dataDir + "/" + STORE_NAME;

    load();
    reconcileNative();

    if ( watchNative && !m_watcher ) {
        m_nativeTimer = new QTimer(this);
        m_nativeTimer->setSingleShot(true);
        m_nativeTimer->setInterval(400);
        connect(m_nativeTimer, &QTimer::timeout, this, &CRecentDocuments::reconcileNative);

        // the engine deletes and rewrites recents.xml, so watch the folder too
        m_watcher = new QFileSystemWatcher(this);
        QDir().mkpath(m_dataDir);
        m_watcher->addPath(m_dataDir);
        const QString native = m_dataDir + "/" + NATIVE_NAME;
        if ( QFileInfo::exists(native) )
            m_watcher->addPath(native);

        connect(m_watcher, &QFileSystemWatcher::directoryChanged, this, [=] { scheduleNativeRead(); });
        connect(m_watcher, &QFileSystemWatcher::fileChanged, this, [=] { scheduleNativeRead(); });
    }

    checkAvailability();
}

QString CRecentDocuments::storePath() const
{
    return m_file;
}

void CRecentDocuments::scheduleNativeRead()
{
    const QString native = m_dataDir + "/" + NATIVE_NAME;
    if ( m_watcher && !m_watcher->files().contains(native) && QFileInfo::exists(native) )
        m_watcher->addPath(native);

    if ( m_nativeTimer ) m_nativeTimer->start();
}

QStringList CRecentDocuments::apps()
{
    return AppIdentity::ids();
}

QString CRecentDocuments::appForPath(const QString& path)
{
    return AppIdentity::appForPath(path);
}

QString CRecentDocuments::key(const QString& path)
{
    QString k = QDir::cleanPath(QDir::fromNativeSeparators(path));
#ifdef Q_OS_WIN
    k = k.toLower();
#endif
    return k;
}

QString CRecentDocuments::now()
{
    return iso(QDateTime::currentDateTimeUtc());
}

QString CRecentDocuments::iso(const QDateTime& dt)
{
    return dt.toUTC().toString(Qt::ISODateWithMs);
}

QDateTime CRecentDocuments::fromIso(const QString& s)
{
    QDateTime dt = QDateTime::fromString(s, Qt::ISODateWithMs);
    if ( !dt.isValid() ) dt = QDateTime::fromString(s, Qt::ISODate);
    return dt;
}

/* storage */

bool CRecentDocuments::loadFile(const QString& file)
{
    QFile f(file);
    if ( !f.open(QIODevice::ReadOnly) )
        return false;

    QJsonParseError err;
    const QJsonDocument doc = QJsonDocument::fromJson(f.readAll(), &err);
    if ( err.error != QJsonParseError::NoError || !doc.isObject() )
        return false;

    QJsonObject root = doc.object();
    if ( !root.value("lists").isObject() )
        return false;

    // drop what can't be an entry, and keep one entry per path
    QJsonObject lists = root.value("lists").toObject();
    for (const QString& app : apps()) {
        QJsonArray in = lists.value(app).toArray(), out;
        QStringList seen;
        for (const QJsonValue& v : in) {
            QJsonObject e = v.toObject();
            const QString path = e.value("path").toString();
            if ( path.isEmpty() || appForPath(path) != app || seen.contains(key(path)) )
                continue;

            seen << key(path);
            e["app"] = app;
            out.append(e);
        }
        sortList(out);
        lists[app] = out;
    }
    root["lists"] = lists;

    m_root = root;
    return true;
}

void CRecentDocuments::load()
{
    m_root = QJsonObject();
    m_backedUp = false;

    if ( loadFile(m_file) ) {
        m_loaded = true;
    } else {
        if ( QFileInfo::exists(m_file) ) {
            // keep the damaged file for inspection, load the last good copy
            const QString aside = m_file + ".corrupt";
            QFile::remove(aside);
            QFile::rename(m_file, aside);
            qWarning() << "recent documents: unreadable store set aside as" << aside;
        }

        if ( loadFile(m_file + ".bak") ) {
            qWarning() << "recent documents: restored from backup";
            m_loaded = true;
            m_backedUp = true;      // the backup is the good copy: don't overwrite it this session
            save();
        }
    }

    if ( !m_root.value("lists").isObject() )
        m_root["lists"] = QJsonObject();

    m_stamp = diskStamp();

    // future schema changes migrate here, keyed on m_root["schema"]
    if ( m_root.value("schema").toInt() < schemaVersion )
        m_root["schema"] = schemaVersion;
}

bool CRecentDocuments::save()
{
    if ( m_file.isEmpty() ) return false;

    QDir().mkpath(m_dataDir);

    // once per session, before the first change, keep the previous file
    if ( !m_backedUp && QFileInfo::exists(m_file) ) {
        const QString bak = m_file + ".bak", tmp = bak + ".tmp";
        QFile::remove(tmp);
        if ( QFile::copy(m_file, tmp) ) {
            QFile::remove(bak);
            QFile::rename(tmp, bak);
        }
    }
    m_backedUp = true;

    m_root["savedAt"] = now();

    QSaveFile f(m_file);
    if ( !f.open(QIODevice::WriteOnly) ) {
        qWarning() << "recent documents: can't write" << m_file << f.errorString();
        return false;
    }

    f.setPermissions(QFileDevice::ReadOwner | QFileDevice::WriteOwner);
    f.write(QJsonDocument(m_root).toJson(QJsonDocument::Indented));
    if ( !syncToDisk(f) ) {
        f.cancelWriting();
        qWarning() << "recent documents: can't flush" << m_file;
        return false;
    }

    const bool ok = f.commit();
    m_stamp = diskStamp();
    return ok;
}

/* lists */

QJsonArray CRecentDocuments::list(const QString& app) const
{
    return m_root.value("lists").toObject().value(app).toArray();
}

void CRecentDocuments::setList(const QString& app, const QJsonArray& list)
{
    QJsonObject lists = m_root.value("lists").toObject();
    lists[app] = list;
    m_root["lists"] = lists;
}

int CRecentDocuments::indexOf(const QJsonArray& list, const QString& k) const
{
    for (int i = 0; i < list.size(); ++i) {
        if ( key(list.at(i).toObject().value("path").toString()) == k )
            return i;
    }
    return -1;
}

void CRecentDocuments::sortList(QJsonArray& list) const
{
    QList<QJsonObject> items;
    for (const QJsonValue& v : list)
        items << v.toObject();

    std::stable_sort(items.begin(), items.end(), [](const QJsonObject& a, const QJsonObject& b) {
        const bool pa = a.value("pinned").toBool(), pb = b.value("pinned").toBool();
        if ( pa != pb ) return pa;
        return a.value("used").toString() > b.value("used").toString();     // ISO UTC strings sort by time
    });

    list = QJsonArray();
    for (const QJsonObject& o : items)
        list.append(o);
}

void CRecentDocuments::trim(const QString& app)
{
    QJsonArray l = list(app);
    sortList(l);

    int unpinned = 0;
    for (int i = 0; i < l.size(); ) {
        if ( !l.at(i).toObject().value("pinned").toBool() && ++unpinned > maxUnpinned )
            l.removeAt(i);
        else ++i;
    }

    setList(app, l);
}

void CRecentDocuments::tombstone(const QString& k, const QDateTime& when)
{
    QJsonObject removed = m_root.value("removed").toObject();
    removed[k] = iso(when);

    if ( removed.size() > MAX_TOMBSTONES ) {
        QList<QPair<QString, QString>> items;
        for (auto it = removed.begin(); it != removed.end(); ++it)
            items << qMakePair(it.value().toString(), it.key());
        std::sort(items.begin(), items.end());
        for (int i = 0; i < items.size() - MAX_TOMBSTONES; ++i)
            removed.remove(items.at(i).second);
    }

    m_root["removed"] = removed;
}

void CRecentDocuments::notify()
{
    emit changed();
}

void CRecentDocuments::registerDocument(const QString& rawPath, Event ev, const QString& origin,
                                        const QString& templateName, const QDateTime& when)
{
    Transaction txn(this);
    if ( rawPath.isEmpty() || isRemote(rawPath) )
        return;

    const QString path = displayPath(rawPath);
    const QString app = appForPath(path);
    if ( app.isEmpty() )
        return;

    const QString k = key(path), t = when.isValid() ? iso(when) : now();

    QJsonObject removed = m_root.value("removed").toObject();
    if ( removed.contains(k) ) {
        removed.remove(k);
        m_root["removed"] = removed;
    }

    QJsonArray l = list(app);
    const int i = indexOf(l, k);

    QJsonObject e;
    if ( i < 0 ) {
        QFileInfo fi(path);
        e["path"] = path;
        e["name"] = fi.fileName();
        e["ext"] = fi.suffix().toLower();
        e["folder"] = QDir::toNativeSeparators(fi.absolutePath());
        e["app"] = app;
        e["created"] = t;
        e["pinned"] = false;
        e["origin"] = !origin.isEmpty() ? origin : (ev == Event::Opened ? "opened" : "new");
        if ( !templateName.isEmpty() )
            e["template"] = templateName;
    } else {
        e = l.at(i).toObject();
        l.removeAt(i);
        e["path"] = path;           // keeps the spelling the file has now
        e["name"] = QFileInfo(path).fileName();
    }

    e["used"] = t;
    e[ev == Event::Opened ? "opened" : "saved"] = t;
    l.prepend(e);

    setList(app, l);
    trim(app);
    m_status.remove(k);

    save();
    notify();
    checkAvailability();
}

bool CRecentDocuments::setPinned(const QString& path, bool pinned)
{
    Transaction txn(this);
    const QString app = appForPath(path), k = key(path);
    QJsonArray l = list(app);
    const int i = indexOf(l, k);
    if ( i < 0 ) return false;

    QJsonObject e = l.at(i).toObject();
    if ( e.value("pinned").toBool() == pinned )
        return true;

    if ( pinned ) {
        int count = 0;
        for (const QJsonValue& v : l)
            count += v.toObject().value("pinned").toBool() ? 1 : 0;
        if ( count >= maxPinned )
            return false;
    }

    e["pinned"] = pinned;
    if ( pinned ) e["pinnedAt"] = now();
    else e.remove("pinnedAt");
    l[i] = e;

    setList(app, l);
    trim(app);
    save();
    notify();
    return true;
}

bool CRecentDocuments::remove(const QString& path)
{
    Transaction txn(this);
    const QString app = appForPath(path), k = key(path);
    QJsonArray l = list(app);
    const int i = indexOf(l, k);
    if ( i < 0 ) return false;

    l.removeAt(i);
    setList(app, l);
    tombstone(k, QDateTime::currentDateTimeUtc());
    m_status.remove(k);

    save();
    notify();
    return true;
}

int CRecentDocuments::clear(const QString& app, bool includePinned)
{
    Transaction txn(this);
    const QStringList targets = app == "suite" ? apps() : (apps().contains(app) ? QStringList{app} : QStringList());
    const QDateTime t = QDateTime::currentDateTimeUtc();

    int count = 0;
    QJsonObject cleared = m_root.value("cleared").toObject();
    for (const QString& a : targets) {
        QJsonArray l = list(a), keep;
        for (const QJsonValue& v : l) {
            const QJsonObject e = v.toObject();
            if ( e.value("pinned").toBool() && !includePinned ) {
                keep.append(e);
            } else {
                m_status.remove(key(e.value("path").toString()));
                ++count;
            }
        }

        setList(a, keep);
        cleared[a] = iso(t);
    }

    if ( targets.isEmpty() ) return 0;

    m_root["cleared"] = cleared;
    save();
    notify();
    return count;
}

bool CRecentDocuments::relocate(const QString& from, const QString& rawTo)
{
    Transaction txn(this);
    if ( rawTo.isEmpty() || isRemote(rawTo) ) return false;

    const QString to = displayPath(rawTo);
    const QString appFrom = appForPath(from), appTo = appForPath(to);
    if ( appTo.isEmpty() ) return false;

    QJsonArray lf = list(appFrom);
    const int i = indexOf(lf, key(from));
    if ( i < 0 ) return false;

    QJsonObject e = lf.at(i).toObject();
    if ( key(from) != key(to) ) {
        lf.removeAt(i);
        setList(appFrom, lf);
        tombstone(key(from), QDateTime::currentDateTimeUtc());
        m_status.remove(key(from));
    }

    QJsonArray lt = list(appTo);
    const int j = indexOf(lt, key(to));
    if ( j >= 0 ) {
        // the new place is already listed: keep that entry, and the pin
        QJsonObject existing = lt.at(j).toObject();
        if ( e.value("pinned").toBool() && !existing.value("pinned").toBool() ) {
            existing["pinned"] = true;
            existing["pinnedAt"] = e.value("pinnedAt");
        }
        lt.removeAt(j);
        e = existing;
    }

    QFileInfo fi(to);
    e["path"] = to;
    e["name"] = fi.fileName();
    e["ext"] = fi.suffix().toLower();
    e["folder"] = QDir::toNativeSeparators(fi.absolutePath());
    e["app"] = appTo;
    e["used"] = now();
    lt.prepend(e);
    setList(appTo, lt);
    trim(appTo);

    QJsonObject removed = m_root.value("removed").toObject();
    removed.remove(key(to));
    m_root["removed"] = removed;

    save();
    notify();
    checkAvailability();
    return true;
}

bool CRecentDocuments::contains(const QString& path) const
{
    return indexOf(list(appForPath(path)), key(path)) >= 0;
}

QJsonObject CRecentDocuments::entry(const QString& path) const
{
    const QJsonArray l = list(appForPath(path));
    const int i = indexOf(l, key(path));
    return i < 0 ? QJsonObject() : l.at(i).toObject();
}

/* availability */

QString CRecentDocuments::status(const QString& path) const
{
    return m_status.value(key(path), "unknown");
}

QString CRecentDocuments::checkPath(const QString& path, qint64 * size, QDateTime * modified)
{
    QFileInfo fi(path);
    if ( fi.exists() ) {
        if ( !fi.isFile() ) return "missing";
        if ( !fi.isReadable() ) return "noaccess";

        if ( size ) *size = fi.size();
        if ( modified ) *modified = fi.lastModified();
        return "ok";
    }

    // a missing folder usually means a removed drive or an unreachable share
    return fi.absoluteDir().exists() ? "missing" : "unreachable";
}

void CRecentDocuments::checkAvailability()
{
    if ( m_checker ) {
        m_recheck = true;
        return;
    }

    QStringList paths;
    for (const QString& app : apps()) {
        for (const QJsonValue& v : list(app))
            paths << v.toObject().value("path").toString();
    }

    if ( paths.isEmpty() ) return;

    // a file on a slow or lost network share can block, so check off the UI thread
    m_checker = QThread::create([this, paths] {
        QHash<QString, QJsonObject> results;
        for (const QString& p : paths) {
            qint64 size = -1;
            QDateTime modified;
            QJsonObject r{{"status", checkPath(p, &size, &modified)}};
            if ( size >= 0 ) r["size"] = double(size);
            if ( modified.isValid() ) r["modified"] = iso(modified);
            results.insert(key(p), r);
        }

        QMetaObject::invokeMethod(this, [this, results] { applyChecks(results); }, Qt::QueuedConnection);
    });

    connect(m_checker, &QThread::finished, this, [this] {
        m_checker->deleteLater();
        m_checker = nullptr;
        if ( m_recheck ) {
            m_recheck = false;
            checkAvailability();
        }
    });
    m_checker->start(QThread::LowPriority);
}

void CRecentDocuments::applyChecks(const QHash<QString, QJsonObject>& results)
{
    Transaction txn(this);
    bool statusChanged = false, metaChanged = false;

    for (auto it = results.cbegin(); it != results.cend(); ++it) {
        const QString st = it.value().value("status").toString();
        if ( m_status.value(it.key()) != st ) {
            m_status[it.key()] = st;
            statusChanged = true;
        }
    }

    for (const QString& app : apps()) {
        QJsonArray l = list(app);
        bool listChanged = false;
        for (int i = 0; i < l.size(); ++i) {
            QJsonObject e = l.at(i).toObject();
            const auto r = results.constFind(key(e.value("path").toString()));
            if ( r == results.cend() || r.value().value("status").toString() != "ok" )
                continue;

            bool entryChanged = false;
            for (const char * f : {"size", "modified"}) {
                if ( r.value().contains(f) && e.value(f) != r.value().value(f) ) {
                    e[f] = r.value().value(f);
                    entryChanged = true;
                }
            }
            if ( entryChanged ) {
                l[i] = e;
                listChanged = true;
            }
        }
        if ( listChanged ) {
            setList(app, l);
            metaChanged = true;
        }
    }

    if ( metaChanged ) save();
    if ( statusChanged || metaChanged ) notify();
}

/* snapshot */

QJsonObject CRecentDocuments::snapshot() const
{
    QJsonObject lists;
    for (const QString& app : apps()) {
        QJsonArray l = list(app), out;
        for (const QJsonValue& v : l) {
            QJsonObject e = v.toObject();
            e["status"] = status(e.value("path").toString());
            out.append(e);
        }
        lists[app] = out;
    }

    return QJsonObject{{"schema", schemaVersion}, {"lists", lists}};
}

QString CRecentDocuments::snapshotJson() const
{
    return QString::fromUtf8(QJsonDocument(snapshot()).toJson(QJsonDocument::Compact));
}

/* the engine's recents.xml */

void CRecentDocuments::reconcileNative()
{
    if ( m_dataDir.isEmpty() ) return;

    Transaction txn(this);
    // another application changed the store: show its lists here too
    if ( m_external ) {
        m_external = false;
        notify();
    }

    QFile f(m_dataDir + "/" + NATIVE_NAME);
    if ( !f.open(QIODevice::ReadOnly) ) {
        if ( !m_root.contains("legacyImported") ) {
            m_root["legacyImported"] = true;
            save();
        }
        return;
    }

    struct NativeItem { QString path; QDateTime date; bool pin; };
    QList<NativeItem> items;

    const QDateTime fileTime = QFileInfo(f).lastModified();
    QXmlStreamReader xml(&f);
    while ( !xml.atEnd() ) {
        if ( xml.readNext() == QXmlStreamReader::StartElement && xml.name() == QLatin1String("file") ) {
            const auto a = xml.attributes();
            const QString path = a.value("path").toString();
            if ( path.isEmpty() || !a.value("url").isEmpty() || isRemote(path) )
                continue;

            QDateTime d = QDateTime::fromString(a.value("date").toString(), "dd.MM.yyyy HH:mm");
            if ( !d.isValid() ) d = fileTime;
            items << NativeItem{path, d, a.value("pin") == QLatin1String("1")};
        }
    }

    if ( xml.hasError() && items.isEmpty() ) {
        qWarning() << "recent documents: recents.xml unreadable:" << xml.errorString();
        return;
    }

    const bool firstRun = !m_root.contains("legacyImported");
    const QJsonObject removed = m_root.value("removed").toObject();
    const QJsonObject cleared = m_root.value("cleared").toObject();

    QStringList touched;
    for (auto it = items.crbegin(); it != items.crend(); ++it) {
        const QString path = displayPath(it->path);
        const QString app = appForPath(path), k = key(path);
        if ( app.isEmpty() ) continue;

        QJsonArray l = list(app);
        const int i = indexOf(l, k);
        if ( i >= 0 ) {
            QJsonObject e = l.at(i).toObject();
            if ( it->date > fromIso(e.value("used").toString()) ) {
                e["used"] = e["opened"] = iso(it->date);
                l[i] = e;
                setList(app, l);
                touched << app;
            }
            continue;
        }

        // not brought back after the user removed it or cleared the list
        const QDateTime rm = fromIso(removed.value(k).toString()),
                        cl = fromIso(cleared.value(app).toString());
        if ( (rm.isValid() && it->date <= rm) || (cl.isValid() && it->date <= cl) )
            continue;

        QFileInfo fi(path);
        QJsonObject e{
            {"path", path}, {"name", fi.fileName()}, {"ext", fi.suffix().toLower()},
            {"folder", QDir::toNativeSeparators(fi.absolutePath())}, {"app", app},
            {"created", iso(it->date)}, {"used", iso(it->date)}, {"opened", iso(it->date)},
            {"origin", firstRun ? "imported" : "opened"},
            {"pinned", firstRun && it->pin},
        };
        if ( firstRun && it->pin ) e["pinnedAt"] = iso(it->date);
        l.append(e);
        setList(app, l);
        touched << app;
    }

    touched.removeDuplicates();
    for (const QString& app : touched)
        trim(app);

    if ( firstRun ) m_root["legacyImported"] = true;
    if ( firstRun || !touched.isEmpty() ) save();
    if ( !touched.isEmpty() ) {
        notify();
        checkAvailability();
    }
}

/* editor views */

void CRecentDocuments::onDocumentName(int viewId, const QString& path, const QString& url)
{
    if ( !url.isEmpty() || isRemote(path) ) return;

    ViewState& v = m_views[viewId];
    if ( path.isEmpty() ) {
        if ( v.path.isEmpty() ) v.isNew = true;
        return;
    }

    const qint64 t = QDateTime::currentMSecsSinceEpoch();
    if ( v.path.isEmpty() ) {
        if ( v.isNew ) registerDocument(path, Event::Saved, v.origin.isEmpty() ? "new" : v.origin, v.templateName);
        else registerDocument(path, Event::Opened, "opened");
    } else
    if ( key(v.path) == key(path) ) {
        // the editor names the document again right after loading it
        if ( t - v.lastEvent < DUPLICATE_EVENT_MS ) return;
        registerDocument(path, Event::Saved);
    } else {
        registerDocument(path, Event::Saved, "saveas");
    }

    v.path = path;
    v.lastEvent = t;
}

void CRecentDocuments::expectTemplate(int viewId, const QString& templatePath)
{
    ViewState& v = m_views[viewId];
    v.isNew = true;
    v.origin = "template";
    v.templateName = QFileInfo(templatePath).completeBaseName();
}

void CRecentDocuments::forgetView(int viewId)
{
    m_views.remove(viewId);
}
