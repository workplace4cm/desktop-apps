#include <QtTest>
#include <QTemporaryDir>
#include <QJsonDocument>
#include "crecentdocuments.h"

using Ev = CRecentDocuments::Event;

class TestRecentDocuments : public QObject
{
    Q_OBJECT

    QTemporaryDir m_dir;
    QString m_data, m_docs;

    QString doc(const QString& name, const QByteArray& content = "x")
    {
        const QString p = m_docs + "/" + name;
        QFile f(p);
        f.open(QIODevice::WriteOnly);
        f.write(content);
        return QDir::toNativeSeparators(p);
    }

    QJsonArray listOf(const CRecentDocuments& r, const QString& app)
    {
        return r.snapshot().value("lists").toObject().value(app).toArray();
    }

    void waitChecks(CRecentDocuments& r, const QString& path, const QString& expect)
    {
        QTRY_COMPARE_WITH_TIMEOUT(r.status(path), expect, 5000);
    }

    void writeNative(const QString& body)
    {
        QFile f(m_data + "/recents.xml");
        f.open(QIODevice::WriteOnly | QIODevice::Truncate);
        f.write(("<?xml version=\"1.0\" encoding=\"utf-8\"?><recents>" + body + "</recents>").toUtf8());
    }

private slots:
    void init()
    {
        QDir(m_dir.path()).removeRecursively();
        QDir().mkpath(m_dir.path());
        m_data = m_dir.path() + "/data";
        m_docs = m_dir.path() + "/docs";
        QDir().mkpath(m_data);
        QDir().mkpath(m_docs);
    }

    void separateListsPerApplication()
    {
        CRecentDocuments r;
        r.init(m_data, false);
        r.registerDocument(doc("a.docx"), Ev::Opened);
        r.registerDocument(doc("b.xlsx"), Ev::Opened);
        r.registerDocument(doc("c.pptx"), Ev::Opened);
        r.registerDocument(doc("d.pdf"), Ev::Opened);
        r.registerDocument(doc("e.zip"), Ev::Opened);           // no application: ignored

        QCOMPARE(listOf(r, "writer").size(), 1);
        QCOMPARE(listOf(r, "sheet").size(), 1);
        QCOMPARE(listOf(r, "presentation").size(), 1);
        QCOMPARE(listOf(r, "pdf").size(), 1);
        QCOMPARE(listOf(r, "writer").at(0).toObject().value("name").toString(), QString("a.docx"));
    }

    void metadataAndNoDuplicates()
    {
        CRecentDocuments r;
        r.init(m_data, false);
        const QString p = doc("report.docx");
        r.registerDocument(p, Ev::Opened);
        QTest::qWait(5);
        r.registerDocument(m_docs + "/./report.docx", Ev::Saved);   // same file, other spelling

        const QJsonArray l = listOf(r, "writer");
        QCOMPARE(l.size(), 1);
        const QJsonObject e = l.at(0).toObject();
        QCOMPARE(e.value("app").toString(), QString("writer"));
        QCOMPARE(e.value("ext").toString(), QString("docx"));
        QCOMPARE(e.value("origin").toString(), QString("opened"));
        QVERIFY(!e.value("created").toString().isEmpty());
        QVERIFY(!e.value("opened").toString().isEmpty());
        QVERIFY(e.value("saved").toString() > e.value("opened").toString());
        QCOMPARE(e.value("used").toString(), e.value("saved").toString());
        QCOMPARE(e.value("folder").toString(), QDir::toNativeSeparators(m_docs));
    }

    void newestFirstPinnedOnTop()
    {
        CRecentDocuments r;
        r.init(m_data, false);
        const QString a = doc("a.docx"), b = doc("b.docx"), c = doc("c.docx");
        r.registerDocument(a, Ev::Opened); QTest::qWait(5);
        r.registerDocument(b, Ev::Opened); QTest::qWait(5);
        r.registerDocument(c, Ev::Opened);
        QVERIFY(r.setPinned(a, true));

        QJsonArray l = listOf(r, "writer");
        QCOMPARE(l.at(0).toObject().value("name").toString(), QString("a.docx"));
        QCOMPARE(l.at(1).toObject().value("name").toString(), QString("c.docx"));
        QVERIFY(l.at(0).toObject().value("pinned").toBool());

        QVERIFY(r.setPinned(a, false));
        l = listOf(r, "writer");
        QCOMPARE(l.at(2).toObject().value("name").toString(), QString("a.docx"));
        QVERIFY(!l.at(2).toObject().contains("pinnedAt"));
    }

    void persistsAfterRestart()
    {
        const QString a = doc("a.docx"), b = doc("b.xlsx");
        {
            CRecentDocuments r;
            r.init(m_data, false);
            r.registerDocument(a, Ev::Opened);
            r.registerDocument(b, Ev::Saved, "template", "Budget");
            r.setPinned(b, true);
        }
        CRecentDocuments r2;
        r2.init(m_data, false);
        QCOMPARE(listOf(r2, "writer").size(), 1);
        const QJsonObject s = listOf(r2, "sheet").at(0).toObject();
        QVERIFY(s.value("pinned").toBool());
        QCOMPARE(s.value("origin").toString(), QString("template"));
        QCOMPARE(s.value("template").toString(), QString("Budget"));
    }

    void removeKeepsTheFile()
    {
        CRecentDocuments r;
        r.init(m_data, false);
        const QString a = doc("a.docx");
        r.registerDocument(a, Ev::Opened);
        QVERIFY(r.remove(a));
        QCOMPARE(listOf(r, "writer").size(), 0);
        QVERIFY(QFile::exists(a));
        QVERIFY(!r.remove(a));
    }

    void clearOneApplication()
    {
        CRecentDocuments r;
        r.init(m_data, false);
        const QString a = doc("a.docx"), b = doc("b.docx"), c = doc("c.xlsx");
        r.registerDocument(a, Ev::Opened);
        r.registerDocument(b, Ev::Opened);
        r.registerDocument(c, Ev::Opened);
        r.setPinned(a, true);

        QCOMPARE(r.clear("writer", false), 1);              // pinned stays
        QCOMPARE(listOf(r, "writer").size(), 1);
        QCOMPARE(listOf(r, "sheet").size(), 1);              // other application untouched
        QCOMPARE(r.clear("writer", true), 1);
        QCOMPARE(listOf(r, "writer").size(), 0);
        QCOMPARE(r.clear("suite", true), 1);
        QCOMPARE(listOf(r, "sheet").size(), 0);
        QVERIFY(QFile::exists(a) && QFile::exists(b) && QFile::exists(c));
    }

    void importsEngineHistoryOnce()
    {
        const QString a = doc("old.docx"), b = doc("old.pptx");
        writeNative(QString("<file path=\"%1\" type=\"65\" date=\"30.10.2026 09:15\" url=\"\" parent=\"\" pin=\"1\" />"
                            "<file path=\"%2\" type=\"129\" date=\"29.10.2026 18:00\" url=\"\" parent=\"\" />"
                            "<file path=\"https://example.org/x.docx\" type=\"65\" date=\"29.10.2026 18:00\" url=\"https://example.org/x.docx\" />")
                    .arg(a.toHtmlEscaped(), b.toHtmlEscaped()));

        CRecentDocuments r;
        r.init(m_data, false);
        QCOMPARE(listOf(r, "writer").size(), 1);
        QCOMPARE(listOf(r, "presentation").size(), 1);
        const QJsonObject e = listOf(r, "writer").at(0).toObject();
        QVERIFY(e.value("pinned").toBool());                 // pins carried over from the old list
        QCOMPARE(e.value("origin").toString(), QString("imported"));

        r.reconcileNative();
        QCOMPARE(listOf(r, "writer").size(), 1);

        // removed entries don't come back from the engine's list ...
        QVERIFY(r.remove(b));
        r.reconcileNative();
        QCOMPARE(listOf(r, "presentation").size(), 0);

        // ... until the document is used again
        writeNative(QString("<file path=\"%1\" type=\"129\" date=\"%2\" url=\"\" />")
                    .arg(b.toHtmlEscaped(), QDateTime::currentDateTime().addSecs(120).toString("dd.MM.yyyy HH:mm")));
        r.reconcileNative();
        QCOMPARE(listOf(r, "presentation").size(), 1);
        QCOMPARE(listOf(r, "presentation").at(0).toObject().value("origin").toString(), QString("opened"));
    }

    void clearedHistoryStaysClear()
    {
        const QString a = doc("a.docx");
        writeNative(QString("<file path=\"%1\" type=\"65\" date=\"30.10.2026 09:15\" url=\"\" />").arg(a.toHtmlEscaped()));
        CRecentDocuments r;
        r.init(m_data, false);
        QCOMPARE(listOf(r, "writer").size(), 1);
        r.clear("writer", true);
        r.reconcileNative();
        QCOMPARE(listOf(r, "writer").size(), 0);
    }

    void survivesDamagedFile()
    {
        const QString a = doc("a.docx"), b = doc("b.docx");
        {
            CRecentDocuments r;
            r.init(m_data, false);
            r.registerDocument(a, Ev::Opened);
        }
        {
            CRecentDocuments r;                   // second session: makes the backup, then writes
            r.init(m_data, false);
            r.registerDocument(b, Ev::Opened);
        }
        QVERIFY(QFile::exists(m_data + "/sos-recents.json.bak"));

        // a crash or a full disk left a broken file
        QFile f(m_data + "/sos-recents.json");
        f.open(QIODevice::WriteOnly | QIODevice::Truncate);
        f.write("{\"lists\": {\"writer\": [");
        f.close();

        CRecentDocuments r;
        r.init(m_data, false);
        QCOMPARE(listOf(r, "writer").size(), 1);              // the previous session's list
        QVERIFY(QFile::exists(m_data + "/sos-recents.json.corrupt"));
        QVERIFY(QFile::exists(m_data + "/sos-recents.json"));
    }

    void keepsFieldsItDoesNotKnow()
    {
        const QString a = doc("a.docx");
        QJsonObject e{{"path", a}, {"name", "a.docx"}, {"used", "2026-10-30T10:00:00.000Z"}, {"futureField", 42}};
        QJsonObject root{{"schema", 7}, {"lists", QJsonObject{{"writer", QJsonArray{e}}}},
                         {"futureTop", "keep"}, {"legacyImported", true}};
        QFile f(m_data + "/sos-recents.json");
        f.open(QIODevice::WriteOnly);
        f.write(QJsonDocument(root).toJson());
        f.close();

        {
            CRecentDocuments r;
            r.init(m_data, false);
            r.setPinned(a, true);
        }
        f.open(QIODevice::ReadOnly);
        const QJsonObject saved = QJsonDocument::fromJson(f.readAll()).object();
        QCOMPARE(saved.value("schema").toInt(), 7);
        QCOMPARE(saved.value("futureTop").toString(), QString("keep"));
        const QJsonObject se = saved.value("lists").toObject().value("writer").toArray().at(0).toObject();
        QCOMPARE(se.value("futureField").toInt(), 42);
        QVERIFY(se.value("pinned").toBool());
    }

    void reportsMissingAndUnreachable()
    {
        CRecentDocuments r;
        r.init(m_data, false);
        const QString ok = doc("ok.docx"), gone = doc("gone.docx");
        const QString lostDrive = m_dir.path() + "/no-such-drive/x.docx";
        r.registerDocument(ok, Ev::Opened);
        r.registerDocument(gone, Ev::Opened);
        r.registerDocument(lostDrive, Ev::Opened);
        QFile::remove(gone);
        r.checkAvailability();

        waitChecks(r, ok, "ok");
        waitChecks(r, gone, "missing");
        waitChecks(r, lostDrive, "unreachable");
        QVERIFY(listOf(r, "writer").size() == 3);            // still listed, marked
        QVERIFY(r.entry(ok).value("size").toDouble() > 0);
    }

    void relocateMovedFile()
    {
        CRecentDocuments r;
        r.init(m_data, false);
        const QString a = doc("a.docx");
        r.registerDocument(a, Ev::Opened);
        r.setPinned(a, true);

        QDir().mkpath(m_docs + "/moved");
        const QString moved = QDir::toNativeSeparators(m_docs + "/moved/renamed.docx");
        QFile::rename(a, moved);

        QVERIFY(r.relocate(a, moved));
        const QJsonArray l = listOf(r, "writer");
        QCOMPARE(l.size(), 1);
        QCOMPARE(l.at(0).toObject().value("name").toString(), QString("renamed.docx"));
        QVERIFY(l.at(0).toObject().value("pinned").toBool());
        r.reconcileNative();
        QCOMPARE(listOf(r, "writer").size(), 1);
    }

    void editorEvents()
    {
        CRecentDocuments r;
        r.init(m_data, false);

        // opened file: the editor names it on load (twice) and on each save
        const QString a = doc("a.docx");
        r.onDocumentName(1, a, QString());
        r.onDocumentName(1, a, QString());
        QJsonObject e = r.entry(a);
        QCOMPARE(e.value("origin").toString(), QString("opened"));
        QVERIFY(!e.contains("saved"));

        // new document from a template, saved for the first time
        r.expectTemplate(2, "/opt/app/converter/templates/sos/writer/business-letter.dotx");
        r.onDocumentName(2, QString(), QString());
        QCOMPARE(listOf(r, "writer").size(), 1);              // untitled: not listed yet
        const QString b = doc("letter.docx");
        r.onDocumentName(2, b, QString());
        e = r.entry(b);
        QCOMPARE(e.value("origin").toString(), QString("template"));
        QCOMPARE(e.value("template").toString(), QString("business-letter"));
        QVERIFY(e.contains("saved"));

        // blank document, saved, then saved as another file
        r.onDocumentName(3, QString(), QString());
        const QString c = doc("blank.xlsx"), d = doc("copy.xlsx");
        r.onDocumentName(3, c, QString());
        QCOMPARE(r.entry(c).value("origin").toString(), QString("new"));
        r.onDocumentName(3, d, QString());
        QCOMPARE(r.entry(d).value("origin").toString(), QString("saveas"));
        QCOMPARE(listOf(r, "sheet").size(), 2);

        // cloud documents are not local recents
        r.onDocumentName(4, "x.docx", "https://example.org/x.docx");
        QCOMPARE(listOf(r, "writer").size(), 2);
    }

    void keepsListBounded()
    {
        CRecentDocuments r;
        r.init(m_data, false);
        const QString pinned = doc("pinned.docx");
        r.registerDocument(pinned, Ev::Opened);
        r.setPinned(pinned, true);
        for (int i = 0; i < CRecentDocuments::maxUnpinned + 10; ++i)
            r.registerDocument(m_docs + QString("/f%1.docx").arg(i), Ev::Opened);

        const QJsonArray l = listOf(r, "writer");
        QCOMPARE(l.size(), CRecentDocuments::maxUnpinned + 1);
        QVERIFY(l.at(0).toObject().value("pinned").toBool());
    }

    void watchesEngineList()
    {
        CRecentDocuments r;
        r.init(m_data, true);
        QSignalSpy spy(&r, &CRecentDocuments::changed);
        const QString a = doc("watched.docx");
        writeNative(QString("<file path=\"%1\" type=\"65\" date=\"%2\" url=\"\" />")
                    .arg(a.toHtmlEscaped(), QDateTime::currentDateTime().toString("dd.MM.yyyy HH:mm")));
        QTRY_VERIFY_WITH_TIMEOUT(r.contains(a), 5000);
    }

    // Writer and Sheet run as separate processes on one store: neither
    // overwrites what the other added
    void twoApplicationsShareTheStore()
    {
        CRecentDocuments writer, sheet;
        writer.init(m_data, false);
        sheet.init(m_data, false);

        writer.registerDocument(doc("w1.docx"), Ev::Opened);
        sheet.registerDocument(doc("s1.xlsx"), Ev::Opened);
        writer.registerDocument(doc("w2.docx"), Ev::Opened);
        sheet.setPinned(doc("s1.xlsx"), true);

        CRecentDocuments reread;
        reread.init(m_data, false);
        QCOMPARE(listOf(reread, "writer").size(), 2);
        QCOMPARE(listOf(reread, "sheet").size(), 1);
        QVERIFY(listOf(reread, "sheet").at(0).toObject().value("pinned").toBool());

        // the Writer process sees Sheet's change when it next touches the store
        writer.remove(doc("w1.docx"));
        QCOMPARE(listOf(writer, "sheet").size(), 1);
        QCOMPARE(listOf(writer, "writer").size(), 1);
    }
};

QTEST_GUILESS_MAIN(TestRecentDocuments)
#include "tst_recentdocuments.moc"
