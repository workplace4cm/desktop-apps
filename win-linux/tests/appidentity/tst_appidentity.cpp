#include <QtTest>
#include <QTemporaryDir>
#include "cappidentity.h"

// SecureOffice Writer, Sheet, Presentation and PDF: which application a launch
// belongs to, and where each document goes
class TestAppIdentity : public QObject
{
    Q_OBJECT

    QString cwd() const { return QDir::tempPath(); }

private slots:
    void cleanup()
    {
        AppIdentity::setCurrent(QString());
    }

    void fourApplications()
    {
        QCOMPARE(AppIdentity::ids(), (QStringList{"writer", "sheet", "presentation", "pdf"}));
        QCOMPARE(AppIdentity::name("writer"), QString("SecureOffice Writer"));
        QCOMPARE(AppIdentity::name("sheet"), QString("SecureOffice Sheet"));
        QCOMPARE(AppIdentity::name("presentation"), QString("SecureOffice Presentation"));
        QCOMPARE(AppIdentity::name("pdf"), QString("SecureOffice PDF"));
        QCOMPARE(AppIdentity::name(""), QString("Secure Office Suite"));
        QVERIFY(!AppIdentity::isApp("suite"));
        QVERIFY(!AppIdentity::isApp("WRITER"));
    }

    void applicationOfAFile_data()
    {
        QTest::addColumn<QString>("path");
        QTest::addColumn<QString>("app");
        QTest::newRow("docx")  << "/home/a/Report.docx"   << "writer";
        QTest::newRow("DOC")   << "C:/Users/a/OLD.DOC"    << "writer";
        QTest::newRow("odt")   << "/x/letter.odt"         << "writer";
        QTest::newRow("rtf")   << "/x/a.rtf"              << "writer";
        QTest::newRow("xlsx")  << "/x/Budget.xlsx"        << "sheet";
        QTest::newRow("csv")   << "/x/data.csv"           << "sheet";
        QTest::newRow("ods")   << "/x/a.ods"              << "sheet";
        QTest::newRow("pptx")  << "/x/Deck.pptx"          << "presentation";
        QTest::newRow("ppsx")  << "/x/show.ppsx"          << "presentation";
        QTest::newRow("odp")   << "/x/a.odp"              << "presentation";
        QTest::newRow("pdf")   << "/x/Form.pdf"           << "pdf";
        QTest::newRow("xps")   << "/x/a.xps"              << "pdf";
        QTest::newRow("djvu")  << "/x/a.djvu"             << "pdf";
        QTest::newRow("zip")   << "/x/a.zip"              << "";
        QTest::newRow("none")  << "/x/README"             << "";
    }

    void applicationOfAFile()
    {
        QFETCH(QString, path);
        QFETCH(QString, app);
        QCOMPARE(AppIdentity::appForPath(path), app);
    }

    void applicationOfALaunch()
    {
        // --app wins over the documents
        QCOMPARE(AppIdentity::appFromArgs({"--app=sheet", "/x/a.docx"}), QString("sheet"));
        QCOMPARE(AppIdentity::appFromArgs({"--app=PDF"}), QString("pdf"));
        // otherwise the first document decides (double-click in a file manager)
        QCOMPARE(AppIdentity::appFromArgs({"/x/a.pptx", "/x/b.docx"}), QString("presentation"));
        QCOMPARE(AppIdentity::appFromArgs({"file:///x/a%20b.xlsx"}), QString("sheet"));
        QCOMPARE(AppIdentity::appFromArgs({"--new:cell"}), QString("sheet"));
        QCOMPARE(AppIdentity::appFromArgs({"--new:form"}), QString("pdf"));
        // nothing: the suite page
        QCOMPARE(AppIdentity::appFromArgs({}), QString());
        QCOMPARE(AppIdentity::appFromArgs({"--app=draw", "--lang=de"}), QString());
        QCOMPARE(AppIdentity::appFromArgs({"oo-office://open|n|x.docx"}), QString());
        QCOMPARE(AppIdentity::appFromArgs({"https://example.com/a.docx"}), QString());
    }

    void documentPaths()
    {
        QCOMPARE(AppIdentity::documentPath("/x/a.docx", "/home"), QString("/x/a.docx"));
        QCOMPARE(AppIdentity::documentPath("a.docx", "/home/u"), QString("/home/u/a.docx"));
        QCOMPARE(AppIdentity::documentPath("../b/a.docx", "/home/u"), QString("/home/b/a.docx"));
        QCOMPARE(AppIdentity::documentPath("file:///x/a%20b.docx", "/home"), QString("/x/a b.docx"));
        QCOMPARE(AppIdentity::documentPath("--app=writer", "/home"), QString());
        QCOMPARE(AppIdentity::documentPath("https://a/b.docx", "/home"), QString());
        QCOMPARE(AppIdentity::documentPath("oo-office:action|x", "/home"), QString());
    }

    // documents go to the application they belong to; the rest stays
    void routing()
    {
        QStringList keep;
        QMap<QString, QStringList> routed;
        AppIdentity::partitionArgs("writer", {"--app=writer", "/x/a.docx", "/x/b.xlsx", "/x/c.pdf",
                                              "/x/d.xlsx", "--new:slide", "--lang=de", "/x/README"},
                                   "/home", keep, routed);
        QCOMPARE(keep, (QStringList{"--app=writer", "/x/a.docx", "--lang=de", "/x/README"}));
        QCOMPARE(routed.keys(), (QStringList{"pdf", "presentation", "sheet"}));
        QCOMPARE(routed["sheet"], (QStringList{QDir::toNativeSeparators("/x/b.xlsx"), QDir::toNativeSeparators("/x/d.xlsx")}));
        QCOMPARE(routed["presentation"], QStringList{"--new:slide"});
        QCOMPARE(routed["pdf"], QStringList{QDir::toNativeSeparators("/x/c.pdf")});
        QVERIFY(AppIdentity::hasDocumentArgs(keep, "/home"));

        // "Writer, open this spreadsheet": nothing is left for Writer
        keep.clear(); routed.clear();
        AppIdentity::partitionArgs("writer", {"--app=writer", "/x/b.xlsx"}, "/home", keep, routed);
        QCOMPARE(keep, QStringList{"--app=writer"});
        QVERIFY(!AppIdentity::hasDocumentArgs(keep, "/home"));
        QCOMPARE(routed.size(), 1);

        // the suite page hosts no documents of the four applications
        keep.clear(); routed.clear();
        AppIdentity::partitionArgs(QString(), {"/x/a.docx", "/x/b.pptx"}, "/home", keep, routed);
        QVERIFY(keep.isEmpty());
        QCOMPARE(routed.keys(), (QStringList{"presentation", "writer"}));
    }

    // each application is its own single instance and taskbar entry
    void separateIdentities()
    {
        QStringList locks, classes, models, desktops, suffixes, icons;
        QList<int> ports;
        for (const QString& id : QStringList{"", "writer", "sheet", "presentation", "pdf"}) {
            AppIdentity::setCurrent(id);
            QCOMPARE(AppIdentity::current(), id);
            locks << AppIdentity::lockName("SecureOfficeSuite");
            classes << AppIdentity::receiverClass("DocEditorsWindowClass");
            models << AppIdentity::userModelId("SecureOfficeSuite.Documents.1");
            desktops << AppIdentity::desktopFileName("secure-office-suite-desktopeditors");
            ports << AppIdentity::instancePort(13012);
            suffixes << AppIdentity::dataSuffix();
            icons << AppIdentity::iconResource();
        }
        QCOMPARE(locks, (QStringList{"SecureOfficeSuite", "SecureOfficeSuite.writer", "SecureOfficeSuite.sheet",
                                     "SecureOfficeSuite.presentation", "SecureOfficeSuite.pdf"}));
        QCOMPARE(models, (QStringList{"SecureOfficeSuite.Documents.1", "SecureOfficeSuite.Writer", "SecureOfficeSuite.Sheet",
                                      "SecureOfficeSuite.Presentation", "SecureOfficeSuite.Pdf"}));
        QCOMPARE(desktops.at(1), QString("secure-office-suite-desktopeditors-writer"));
        QCOMPARE(ports, (QList<int>{13012, 13013, 13014, 13015, 13016}));
        QCOMPARE(suffixes, (QStringList{"", "-writer", "-sheet", "-presentation", "-pdf"}));
        QCOMPARE(icons.at(4), QString(":/sos/apps/pdf.svg"));
        QCOMPARE(QSet<QString>(classes.begin(), classes.end()).size(), 5);

        // the installers use the same names (package/inno, package/common/linux)
        AppIdentity::setCurrent("sheet");
        QCOMPARE(AppIdentity::windowTitle(), QString("SecureOffice Sheet"));
        QCOMPARE(AppIdentity::windowTitle("Budget.xlsx"), QString("Budget.xlsx - SecureOffice Sheet"));
        AppIdentity::setCurrent("nonsense");
        QCOMPARE(AppIdentity::current(), QString());
    }

    // the Linux .desktop files and the Windows installer claim the same file
    // types the program routes by
    void packagesAgree()
    {
        const QString root = QFINDTESTDATA("../../../package");
        if ( root.isEmpty() )
            QSKIP("package folder not found");

        QFile iss(root + "/inno/_code.iss");
        QVERIFY(iss.open(QIODevice::ReadOnly));
        const QString code = QString::fromUtf8(iss.readAll());
        QRegularExpression ext("AudioExts\\[(\\d+)\\]\\s*:= '([A-Z0-9]+)';");
        QRegularExpression info("^\\s*ExtensionRegistryInfo\\[(\\d+)\\][^\\n]*'([a-z]+)';", QRegularExpression::MultilineOption);
        QMap<QString, QString> exts, owners;
        for (auto m = ext.globalMatch(code); m.hasNext();) { auto x = m.next(); exts[x.captured(1)] = x.captured(2).toLower(); }
        for (auto m = info.globalMatch(code); m.hasNext();) { auto x = m.next(); owners[x.captured(1)] = x.captured(2); }
        QVERIFY(exts.size() > 20);
        for (auto it = exts.cbegin(); it != exts.cend(); ++it) {
            const QString owner = owners.value(it.key());
            QVERIFY2(!owner.isEmpty(), qPrintable(it.value()));
            QCOMPARE(owner == "suite" ? QString() : owner, AppIdentity::appForExtension(it.value()));
        }
    }
};

QTEST_GUILESS_MAIN(TestAppIdentity)
#include "tst_appidentity.moc"
