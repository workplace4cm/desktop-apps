/*
 * Secure Office Suite: recent documents
 *
 * One local service keeps a separate recent list for each application
 * (EuroOffice Writer, Sheet, Presentation and PDF) in the user's profile
 * folder, next to the editor engine's own recents.xml:
 *
 *  - documents are registered when they are opened, when a new or
 *    template-based document is first saved and on every later save;
 *  - each entry keeps the path, application, origin, the times it was
 *    added, opened, saved and last used, pin state, and the file's size and
 *    modification time from the last check;
 *  - one path is one entry: paths are compared after normalisation
 *    (case-insensitively on Windows);
 *  - pin, unpin, remove, clear and relocate change the list only, never the
 *    document on disk;
 *  - the file is written atomically (temporary file + rename, flushed to
 *    disk) and the previous session's file is kept as a backup. A damaged
 *    file is set aside and the backup, or else the engine's recents.xml, is
 *    loaded instead. Fields this version doesn't know are kept on save, so
 *    a newer or older version of the suite can read the same file.
 *
 * The engine's recents.xml stays the record of what the editors opened and
 * saved; it is read at start and whenever it changes, so nothing is missed
 * when a document was opened while no start page was showing. Removed and
 * cleared entries leave a dated marker so that reading recents.xml doesn't
 * bring them back.
 */

#ifndef CRECENTDOCUMENTS_H
#define CRECENTDOCUMENTS_H

#include <QObject>
#include <QJsonObject>
#include <QJsonArray>
#include <QDateTime>
#include <QHash>
#include <QMap>
#include <QStringList>

class QFileSystemWatcher;
class QTimer;
class QThread;

class CRecentDocuments : public QObject
{
    Q_OBJECT

public:
    enum class Event { Opened, Saved };

    static constexpr int schemaVersion = 1;
    static constexpr int maxUnpinned = 50;
    static constexpr int maxPinned = 100;

    static CRecentDocuments& instance();

    explicit CRecentDocuments(QObject * parent = nullptr);
    ~CRecentDocuments();

    // dataDir holds recents.xml; the service keeps sos-recents.json there
    void init(const QString& dataDir, bool watchNative = true);
    QString storePath() const;

    // "writer", "sheet", "presentation", "pdf", or empty for other files
    static QString appForPath(const QString& path);
    static QStringList apps();
    static QString key(const QString& path);

    // registers a document; origin is "opened", "new", "template" or "saveas"
    void registerDocument(const QString& path, Event ev, const QString& origin = QString(),
                          const QString& templateName = QString(), const QDateTime& when = QDateTime());

    bool setPinned(const QString& path, bool pinned);
    bool remove(const QString& path);
    int  clear(const QString& app, bool includePinned);    // app "suite" clears every list
    bool relocate(const QString& from, const QString& to);
    bool contains(const QString& path) const;
    QJsonObject entry(const QString& path) const;

    // "ok", "missing" (folder there, file not), "unreachable" (folder or drive
    // not there), "noaccess" (can't be read) or "unknown" (not checked yet)
    QString status(const QString& path) const;
    static QString checkPath(const QString& path, qint64 * size = nullptr, QDateTime * modified = nullptr);
    void checkAvailability();

    // {"schema":1, "lists": {"writer": [...], ...}} with each entry's status
    QJsonObject snapshot() const;
    QString snapshotJson() const;

    // reads the engine's recents.xml and adds what's new there
    void reconcileNative();

    // editor views report their document's name and path (empty for an
    // unsaved new document); the first path a new view gets is its first save
    void onDocumentName(int viewId, const QString& path, const QString& url);
    void expectTemplate(int viewId, const QString& templatePath);
    void forgetView(int viewId);

signals:
    void changed();

private:
    struct ViewState {
        QString path;
        bool isNew = false;
        QString origin;
        QString templateName;
        qint64 lastEvent = 0;
    };

    void load();
    bool loadFile(const QString& file);
    bool save();
    void importLegacy(bool firstRun);
    void trim(const QString& app);
    void sortList(QJsonArray& list) const;
    int  indexOf(const QJsonArray& list, const QString& key) const;
    QJsonArray list(const QString& app) const;
    void setList(const QString& app, const QJsonArray& list);
    void tombstone(const QString& key, const QDateTime& when);
    void notify();
    void scheduleNativeRead();
    void applyChecks(const QHash<QString, QJsonObject>& results);

    static QString now();
    static QString iso(const QDateTime& dt);
    static QDateTime fromIso(const QString& s);

    QString m_dataDir;
    QString m_file;
    QJsonObject m_root;
    bool m_backedUp = false;
    bool m_loaded = false;
    QHash<QString, QString> m_status;           // key -> status
    QHash<int, ViewState> m_views;
    QFileSystemWatcher * m_watcher = nullptr;
    QTimer * m_nativeTimer = nullptr;
    QThread * m_checker = nullptr;
    bool m_recheck = false;
};

#endif // CRECENTDOCUMENTS_H
