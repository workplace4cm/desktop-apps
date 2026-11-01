#include <QtTest>
#include <QTemporaryDir>
#include <QJsonDocument>
#include <QRegularExpression>
#include "ctemplatelibrary.h"
#ifndef Q_OS_WIN
# include <unistd.h>
#endif

using St = CTemplateLibrary::Status;

class TestTemplateLibrary : public QObject
{
    Q_OBJECT

    QTemporaryDir m_dir;

    QString copy(const QString& from, const QString& to)
    {
        const QString p = m_dir.path() + "/" + to;
        QDir().mkpath(QFileInfo(p).absolutePath());
        QFile::remove(p);
        if ( !QFile::copy(from, p) )
            qFatal("copy failed: %s", qPrintable(from));
        QFile(p).setPermissions(QFile::ReadOwner | QFile::WriteOwner);
        return p;
    }

    QString write(const QString& to, const QByteArray& data)
    {
        const QString p = m_dir.path() + "/" + to;
        QDir().mkpath(QFileInfo(p).absolutePath());
        QFile f(p);
        f.open(QIODevice::WriteOnly | QIODevice::Truncate);
        f.write(data);
        return p;
    }

    static QString sos(const QString& rel) { return QString(TEMPLATES) + "/sos/" + rel; }

    // the start page's own list: the JSON block of sos/manifest.js
    static QJsonArray manifest()
    {
        QFile f(sos("manifest.js"));
        f.open(QIODevice::ReadOnly);
        const QString js = QString::fromUtf8(f.readAll());
        const QRegularExpression re("/\\*\\s*sos-templates:begin\\s*\\*/(.*)/\\*\\s*sos-templates:end\\s*\\*/",
                                    QRegularExpression::DotMatchesEverythingOption);
        const auto m = re.match(js);
        return QJsonDocument::fromJson(m.captured(1).toUtf8()).object().value("templates").toArray();
    }

private slots:
    void init()
    {
        QDir(m_dir.path()).removeRecursively();
        QDir().mkpath(m_dir.path());
        CTemplateLibrary::setLibraryFolders(TEMPLATES, m_dir.path() + "/My Templates");
    }

    void everyShippedTemplateIsValid()
    {
        const QJsonArray list = manifest();
        QVERIFY(list.size() >= 40);
        for (const QJsonValue& v : list) {
            const QJsonObject t = v.toObject();
            const QString path = QDir::cleanPath(sos(t["file"].toString()));
            QVERIFY2(CTemplateLibrary::isLibraryPath(path), qPrintable(path));
            QCOMPARE(CTemplateLibrary::appForTemplate(path), t["app"].toString());
            const St st = CTemplateLibrary::validate(path, t["app"].toString());
            QVERIFY2(st == St::Ok, qPrintable(t["id"].toString() + ": " + CTemplateLibrary::statusName(st)));
        }
    }

    void otherFormats()
    {
        QCOMPARE(CTemplateLibrary::validate(FIXTURES "/letter.ott"), St::Ok);
        QCOMPARE(CTemplateLibrary::validate(FIXTURES "/budget.ots"), St::Ok);
        QCOMPARE(CTemplateLibrary::validate(FIXTURES "/memo.dot"), St::Ok);
        QCOMPARE(CTemplateLibrary::appForTemplate("x/a.OTT"), QString("writer"));
        QCOMPARE(CTemplateLibrary::appForTemplate("a.xlt"), QString("sheet"));
        QCOMPARE(CTemplateLibrary::appForTemplate("a.potx"), QString("presentation"));
        QCOMPARE(CTemplateLibrary::appForTemplate("a.docx"), QString());
        QCOMPARE(CTemplateLibrary::extensions("writer"), QStringList({"dot", "dotx", "ott"}));
    }

    void missingAndUnreadable()
    {
        QCOMPARE(CTemplateLibrary::validate(m_dir.path() + "/none.dotx"), St::Missing);
        QCOMPARE(CTemplateLibrary::validate(QString()), St::Missing);
        QCOMPARE(CTemplateLibrary::validate(m_dir.path()), St::Missing);   // a folder
#ifndef Q_OS_WIN
        if ( geteuid() != 0 ) {
            const QString p = copy(sos("writer/memo.dotx"), "locked.dotx");
            QFile(p).setPermissions(QFileDevice::Permissions());
            QCOMPARE(CTemplateLibrary::validate(p), St::NoAccess);
        }
#endif
    }

    void damaged()
    {
        QFile src(sos("writer/memo.dotx"));
        src.open(QIODevice::ReadOnly);
        const QByteArray full = src.readAll();

        QCOMPARE(CTemplateLibrary::validate(write("empty.dotx", "")), St::Empty);
        QCOMPARE(CTemplateLibrary::validate(write("half.dotx", full.left(full.size() / 2))), St::Damaged);
        QCOMPARE(CTemplateLibrary::validate(write("tail.dotx", full.mid(100))), St::Damaged);
        QCOMPARE(CTemplateLibrary::validate(write("text.dotx", "hello, this is not a template")), St::Damaged);
        // central directory intact but local headers moved: still caught
        QByteArray shifted = QByteArray(16, '\0') + full;
        QCOMPARE(CTemplateLibrary::validate(write("shifted.dotx", shifted)), St::Damaged);
        QCOMPARE(CTemplateLibrary::validate(write("not.pdf", "%PDF-1.7\n" + QByteArray(200, 'x'))), St::Damaged);
        QCOMPARE(CTemplateLibrary::validate(write("ok.pdf", "%PDF-1.7\n" + QByteArray(200, 'x') + "\n%%EOF\n")), St::Ok);
        QCOMPARE(CTemplateLibrary::validate(write("bad.dot", QByteArray(4096, 'x'))), St::Damaged);
    }

    void wrongApplicationOrFormat()
    {
        // a workbook renamed to .dotx
        QCOMPARE(CTemplateLibrary::validate(copy(sos("sheet/budget.xltx"), "budget.dotx")), St::WrongType);
        // an OpenDocument spreadsheet template renamed to .ott
        QCOMPARE(CTemplateLibrary::validate(copy(FIXTURES "/budget.ots", "budget.ott")), St::WrongType);
        // a Writer template asked for by Sheet
        QCOMPARE(CTemplateLibrary::validate(sos("writer/memo.dotx"), "sheet"), St::WrongType);
        QCOMPARE(CTemplateLibrary::validate(copy(sos("writer/memo.dotx"), "memo.docx")), St::WrongType);
    }

    void macrosAreRefused()
    {
        QCOMPARE(CTemplateLibrary::validate(FIXTURES "/macro.dotx"), St::Macros);
        QCOMPARE(CTemplateLibrary::validate(copy(sos("writer/memo.dotx"), "memo.dotm")), St::Macros);
        QVERIFY(!CTemplateLibrary::extensions("sheet").contains("xltm"));
    }

    void onlyLibraryPaths()
    {
        const QString user = CTemplateLibrary::userFolder();
        const QString mine = copy(sos("writer/memo.dotx"), "My Templates/memo.dotx");
        const QString outside = copy(sos("writer/memo.dotx"), "Downloads/memo.dotx");
        QVERIFY(CTemplateLibrary::isLibraryPath(mine));
        QVERIFY(CTemplateLibrary::isLibraryPath(sos("writer/memo.dotx")));
        QVERIFY(!CTemplateLibrary::isLibraryPath(outside));
        QVERIFY(!CTemplateLibrary::isLibraryPath(user + "/../Downloads/memo.dotx"));
        QVERIFY(!CTemplateLibrary::isLibraryPath(user + "-evil/memo.dotx"));
#ifndef Q_OS_WIN
        QVERIFY(QFile::link(outside, user + "/link.dotx"));
        QVERIFY(!CTemplateLibrary::isLibraryPath(user + "/link.dotx"));
#endif
        const QJsonObject st = CTemplateLibrary::check(QJsonArray{
            QJsonObject{{"id", "a"}, {"path", mine}, {"app", "writer"}},
            QJsonObject{{"id", "b"}, {"path", outside}, {"app", "writer"}},
            QJsonObject{{"id", "c"}, {"path", user + "/gone.dotx"}, {"app", "writer"}},
            QJsonObject{{"id", "d"}, {"path", mine}, {"app", "presentation"}}});
        QCOMPARE(st["a"].toString(), QString("ok"));
        QCOMPARE(st["b"].toString(), QString("outside"));
        QCOMPARE(st["c"].toString(), QString("missing"));
        QCOMPARE(st["d"].toString(), QString("wrongtype"));
    }

    void myTemplatesFolder()
    {
        const QString user = CTemplateLibrary::userFolder();
        QVERIFY(!QDir(user).exists());
        QVERIFY(CTemplateLibrary::scanUserFolder().isEmpty());
        QVERIFY(CTemplateLibrary::ensureUserFolder());
        QVERIFY(QFile::exists(user + "/README.txt"));

        copy(sos("writer/memo.dotx"), "My Templates/Team memo.dotx");
        copy(sos("thumbs/writer-memo.png"), "My Templates/Team memo.png");
        copy(sos("sheet/budget.xltx"), "My Templates/Finance/Quarter budget.xltx");
        copy(FIXTURES "/letter.ott", "My Templates/Finance/Letter.ott");
        write("My Templates/Broken.potx", "not a zip at all");
        copy(sos("writer/memo.dotx"), "My Templates/~$Team memo.dotx");          // Office lock file
        copy(sos("writer/memo.dotx"), "My Templates/a/b/too deep.dotx");
        write("My Templates/form.pdf", "%PDF-1.7\n%%EOF\n");
        write("My Templates/notes.txt", "x");

        const QJsonArray list = CTemplateLibrary::scanUserFolder();
        QStringList names;
        for (const QJsonValue& v : list)
            names << v.toObject()["name"].toString();
        QCOMPARE(names, QStringList({"Broken", "Team memo", "Letter", "Quarter budget"}));

        const QJsonObject memo = list.at(1).toObject();
        QCOMPARE(memo["app"].toString(), QString("writer"));
        QCOMPARE(memo["status"].toString(), QString("ok"));
        QCOMPARE(memo["category"].toString(), QString());
        QVERIFY(memo["thumb"].toString().startsWith("file:"));
        QVERIFY(memo["user"].toBool());
        QCOMPARE(list.at(0).toObject()["status"].toString(), QString("damaged"));
        QCOMPARE(list.at(3).toObject()["category"].toString(), QString("Finance"));
        QCOMPARE(list.at(3).toObject()["app"].toString(), QString("sheet"));
        for (const QJsonValue& v : list)
            QVERIFY(CTemplateLibrary::isLibraryPath(v.toObject()["path"].toString()));
    }

    // File > New in the editors: the manifest read by the shell
    void installedTemplatesFollowTheManifest()
    {
        const QJsonArray list = manifest();
        for (const QString app : {"writer", "sheet", "presentation", "pdf"}) {
            int expected = 0;
            for (const QJsonValue& v : list)
                expected += v.toObject()["app"].toString() == app;

            const QJsonArray got = CTemplateLibrary::installedTemplates(app);
            QCOMPARE(got.size(), expected);
            QVERIFY(expected > 0);
            for (const QJsonValue& v : got) {
                const QJsonObject t = v.toObject();
                QCOMPARE(t["app"].toString(), app);
                QCOMPARE(t["status"].toString(), QString("ok"));
                QVERIFY(!t["name"].toString().isEmpty());
                QVERIFY(QFileInfo(t["path"].toString()).isAbsolute());
                QVERIFY(QFileInfo::exists(t["path"].toString()));
                QVERIFY(CTemplateLibrary::isLibraryPath(t["path"].toString()));
                QVERIFY(t["thumb"].toString().startsWith("file:"));
                QVERIFY(QFileInfo::exists(QUrl(t["thumb"].toString()).toLocalFile()));
            }
        }
        QCOMPARE(CTemplateLibrary::installedTemplates().size(), list.size());
    }

    void templatesForAnApplication()
    {
        copy(FIXTURES "/letter.ott", "My Templates/Letter.ott");
        write("My Templates/Broken.dotx", "PK\x03\x04 not a package");
        copy(FIXTURES "/budget.ots", "My Templates/Budget.ots");

        const QJsonArray writer = CTemplateLibrary::templatesFor("writer");
        QCOMPARE(writer.size(), CTemplateLibrary::installedTemplates("writer").size() + 1);
        QCOMPARE(writer.last().toObject()["name"].toString(), QString("Letter"));
        QVERIFY(writer.last().toObject()["user"].toBool());
        for (const QJsonValue& v : writer) {
            QCOMPARE(v.toObject()["app"].toString(), QString("writer"));
            QCOMPARE(v.toObject()["status"].toString(), QString("ok"));
        }

        const QJsonArray sheet = CTemplateLibrary::templatesFor("sheet");
        QCOMPARE(sheet.last().toObject()["name"].toString(), QString("Budget"));
        QCOMPARE(CTemplateLibrary::templatesFor("nothing").size(), 0);
    }

    void badManifest()
    {
        QCOMPARE(CTemplateLibrary::installedTemplates("writer", write("m1.js", "var x = 1;")).size(), 0);
        QCOMPARE(CTemplateLibrary::installedTemplates("writer",
                    write("m2.js", "/* sos-templates:begin */ {broken /* sos-templates:end */")).size(), 0);
        // an entry pointing outside the library is never offered
        const QString m = write("lib/m3.js", "/* sos-templates:begin */ {\"templates\": ["
                                "{\"id\": \"writer.x\", \"app\": \"writer\", \"name\": \"X\", \"file\": \"../../x.dotx\"}]}"
                                " /* sos-templates:end */");
        copy(FIXTURES "/letter.ott", "x.dotx");
        const QJsonArray got = CTemplateLibrary::installedTemplates("writer", m);
        QCOMPARE(got.size(), 1);
        QVERIFY(got.at(0).toObject()["status"].toString() != "ok");
        QCOMPARE(CTemplateLibrary::installedTemplates("writer", m_dir.path() + "/none.js").size(), 0);
    }

    void messages()
    {
        for (St s : {St::Missing, St::NoAccess, St::Empty, St::TooLarge, St::Damaged, St::WrongType, St::Macros})
            QVERIFY(CTemplateLibrary::statusMessage(s, "<a>.dotx").contains("&lt;a&gt;.dotx"));
        QVERIFY(CTemplateLibrary::statusMessage(St::Ok, "a").isEmpty());
    }
};

QTEST_MAIN(TestTemplateLibrary)
#include "tst_templatelibrary.moc"
