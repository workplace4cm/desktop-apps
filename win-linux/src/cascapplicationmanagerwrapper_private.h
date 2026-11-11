/*
 * (c) Copyright Ascensio System SIA 2010-2019
 *
 * This program is a free software product. You can redistribute it and/or
 * modify it under the terms of the GNU Affero General Public License (AGPL)
 * version 3 as published by the Free Software Foundation. In accordance with
 * Section 7(a) of the GNU AGPL its Section 15 shall be amended to the effect
 * that Ascensio System SIA expressly excludes the warranty of non-infringement
 * of any third-party rights.
 *
 * This program is distributed WITHOUT ANY WARRANTY; without even the implied
 * warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR  PURPOSE. For
 * details, see the GNU AGPL at: http://www.gnu.org/licenses/agpl-3.0.html
 *
 * The  interactive user interfaces in modified source and object code versions
 * of the Program must display Appropriate Legal Notices, as required under
 * Section 5 of the GNU AGPL version 3.
 *
 * All the Product's GUI elements, including illustrations and icon sets, as
 * well as technical writing content are licensed under the terms of the
 * Creative Commons Attribution-ShareAlike 4.0 International. See the License
 * terms at http://creativecommons.org/licenses/by-sa/4.0/legalcode
 *
*/

#ifndef CASCAPPLICATIONMANAGERWRAPPER_PRIVATE_H
#define CASCAPPLICATIONMANAGERWRAPPER_PRIVATE_H

#include "cascapplicationmanagerwrapper.h"
#include "qcefview_media.h"
#include "defines.h"
#include "clangater.h"
#include "cappeventfilter.h"
#include "OfficeFileFormats.h"
#include "ceditortools.h"
#include "utils.h"
#include "components/cmessage.h"
#include "cprintdata.h"
#include "clogger.h"
#include "common/File.h"
#include "crecentdocuments.h"
#include "ctemplatelibrary.h"
#include "cfilechecker.h"
#include <QDesktopServices>
#include <QTimer>
#include <QUrl>
#include <QApplication>
#include <QJsonParseError>
#ifdef _WIN32
# define APP_LAUNCH_NAME "\\DesktopEditors.exe"
# define RESTART_BATCH "/apprestart.bat"
#else
# include "platform_linux/linux_window_utils.h"
# include <QProcess>
# include <unistd.h>
# include <sys/types.h>
# define APP_LAUNCH_NAME "/DesktopEditors"
# define RESTART_BATCH "/apprestart.sh"
#endif

#ifdef DOCUMENTSCORE_OPENSSL_SUPPORT
# include "platform_linux/cdialogopenssl.h"
#endif


class CAscApplicationManagerWrapper_Private
{
public:
    CAscApplicationManagerWrapper_Private(CAscApplicationManagerWrapper * manager)
        : m_appmanager(*manager)
    {
        qApp->installEventFilter(new CAppEventFilter(this));

        GET_REGISTRY_USER(reg_user);
        m_openEditorWindow = reg_user.value("editorWindowMode").toBool();
        m_printData = std::make_shared<CPrintData>();
    }

    virtual ~CAscApplicationManagerWrapper_Private() {}

    virtual void initializeApp() {
        m_printData->setAppDataPath(m_appmanager.m_oSettings.app_data_path);
    }
    virtual bool processEvent(NSEditorApi::CAscCefMenuEvent * event) {
        if ( detectDocumentOpening(*event) )
            return true;

        return false;
    }
    virtual void applyStylesheets() {}
    virtual void addStylesheets(CScalingFactor f, const std::string& s)
    {
        m_appmanager.addStylesheets(f, s);
    }

    virtual QCefView * createView(QWidget * parent, const QSize& s)
    {
        return new QCefView_Media(parent, s + QSize(1,0));
    }

    bool allowedCreateLocalFile()
    {
        return true;
    }

    virtual void init()
    {
    }

    void restartApp()
    {
        const QString fileName = QDir::tempPath() + RESTART_BATCH;
        if (QFile::exists(fileName) && !QFile::remove(fileName)) {
            CLogger::log("An error occurred while deleting: " + fileName);
            return;
        }
        QFile f(fileName);
        if (f.open(QIODevice::WriteOnly | QIODevice::Text)) {
            QTextStream ts(&f);
#ifdef _WIN32
            ts << "@chcp 65001>nul\n";
            ts << "@echo off\n";
            ts << "start \"\" \"" << QString::fromStdWString(NSFile::GetProcessDirectory()) << APP_LAUNCH_NAME << "\"\n";
            ts << "del \"%~f0\"&exit\n";
#else
            ts << "#!/bin/bash\n";
            ts << "sleep 1\n";
            QString appDir = QString::fromStdWString(NSFile::GetProcessDirectory());
            ts << "cd \"" << appDir << "\"\n";
            ts << "LD_LIBRARY_PATH=\"$PWD:$PWD/converter:$LD_LIBRARY_PATH\"";
            ts << " LD_PRELOAD=libcef.so";
            ts << " \"" << appDir << APP_LAUNCH_NAME << "\" &\n";
            ts << "rm -- \"$0\"\n";
#endif
            if (!f.flush()) {
                CLogger::log("An error occurred while writing: " + fileName);
                f.close();
                return;
            }
            f.close();
        } else {
            CLogger::log("An error occurred while creating: " + fileName);
            return;
        }
#ifdef _WIN32
        STARTUPINFO si;
        PROCESS_INFORMATION pi;
        ZeroMemory(&si, sizeof(si));
        ZeroMemory(&pi, sizeof(pi));
        si.cb = sizeof(si);
        if (!CreateProcess(NULL, const_cast<LPWSTR>(fileName.toStdWString().c_str()), NULL, NULL, FALSE,
                           CREATE_NO_WINDOW | CREATE_UNICODE_ENVIRONMENT, NULL, NULL, &si, &pi)) {
            CLogger::log("An error occurred while restarting the app!");
            return;
        }
        CloseHandle(pi.hProcess);
        CloseHandle(pi.hThread);
#else
        // Use fork/exec instead of QProcess::startDetached because
        // this runs from a destructor after Qt's event loop has stopped,
        // where QProcess may not work reliably.
        // Build argv before fork(): the process is multi-threaded (CEF), so the
        // child may only call async-signal-safe functions -- no allocation.
        const QByteArray script = fileName.toLocal8Bit();
        pid_t pid = fork();
        if (pid == 0) {
            setsid();
            execl("/bin/sh", "/bin/sh", script.constData(), (char *)nullptr);
            _exit(1);
        } else if (pid < 0) {
            CLogger::log("An error occurred while restarting the app!");
        }
#endif
    }

//    auto createStartPanel() -> void {
//        GET_REGISTRY_USER(reg_user)

//        m_pStartPanel = AscAppManager::createViewer(nullptr, QSize());
//        m_pStartPanel->Create(&m_appmanager, cvwtSimple);
//        m_pStartPanel->setObjectName("mainPanel");

//        QString data_path;
//#if defined(QT_DEBUG)
//        data_path = reg_user.value("startpage").value<QString>();
//#endif

//        if ( data_path.isEmpty() )
//            data_path = qApp->applicationDirPath() + "/index.html";

//        QString additional = "?waitingloader=yes&lang=" + CLangater::getCurrentLangCode();
//        QString _portal = reg_user.value("portal").value<QString>();
//        if (!_portal.isEmpty()) {
//            QString arg_portal = (additional.isEmpty() ? "?portal=" : "&portal=") + _portal;
//            additional.append(arg_portal);
//        }

//        std::wstring start_path = ("file:///" + data_path + additional).toStdWString();
//        m_pStartPanel->GetCefView()->load(start_path);
//    }

    auto sendOpenFolderEvent(int id) -> void {
        if (!mainWindow() || mainWindow()->startPanelId() != id) {   // Ignore start page
            NSEditorApi::CAscCefMenuEvent * ns_event = new NSEditorApi::CAscCefMenuEvent(ASC_MENU_EVENT_TYPE_CEF_EXECUTE_COMMAND);
            NSEditorApi::CAscExecCommand * pData = new NSEditorApi::CAscExecCommand;
            pData->put_Command(L"open:folder");
            ns_event->m_pData = pData;
            ns_event->m_nSenderId = id;
            m_appmanager.OnEvent(ns_event);
        }
    }

    auto handleAppKeyPress(QKeyEvent * e) -> bool
    {
        if (e->key() == Qt::Key_O && (e->modifiers() & Qt::ControlModifier)) {
            //sendOpenFolderEvent(-1);
            return true;
        }

        return false;
    }

    auto preferOpenEditorWindow() -> bool
    {
        return m_openEditorWindow;
    }

    auto detectDocumentOpening(const NSEditorApi::CAscCefMenuEvent& event) -> bool
    {
        switch ( event.m_nType ) {
        case ASC_MENU_EVENT_TYPE_CEF_CREATETAB: {
            NSEditorApi::CAscCreateTab & data = *static_cast<NSEditorApi::CAscCreateTab *>(event.m_pData);
//            data.get_Active();

            COpenOptions opts{data.get_Url()};
            //            opts.id = data.get_IdEqual();
            opts.parent_id = event.m_nSenderId;
            opts.name = QString::fromStdWString(data.get_Name());

            if ( !bringEditorToFront(QString::fromStdWString(opts.wurl)) )
                openDocument(opts);

            return true;
        }
        case ASC_MENU_EVENT_TYPE_CEF_EXECUTE_COMMAND: {
            NSEditorApi::CAscExecCommand & data = *static_cast<NSEditorApi::CAscExecCommand *>(event.m_pData);
            const std::wstring & cmd = data.get_Command();

            if ( cmd.rfind(L"sos:recents:", 0) == 0 ) {
                handleRecentsCommand(cmd.substr(12), data.get_Param(), event.m_nSenderId);
                return true;
            } else
            if ( cmd.rfind(L"sos:templates:", 0) == 0 ) {
                handleTemplatesCommand(cmd.substr(14), data.get_Param(), event.m_nSenderId);
                return true;
            } else
            if ( cmd.rfind(L"sos:backstage:", 0) == 0 ) {
                handleBackstageCommand(cmd.substr(14), data.get_Param(), event.m_nSenderId);
                return true;
            } else
            if ( cmd.compare(L"open:recent") == 0 ) {
                QJsonObject objRoot = Utils::parseJsonString(data.get_Param());
                if ( !objRoot.isEmpty() ) {
                    QString _path = objRoot["path"].toString();
                    if ( bringEditorToFront( _path ) )
                        return true;

                    bool _from_recovery = objRoot["recovery"].toBool(false);
                    COpenOptions opts{_path.toStdWString(), _from_recovery ? etRecoveryFile : etRecentFile, objRoot["id"].toInt()};
                    opts.format = objRoot["type"].toInt();
                    opts.parent_id = event.m_nSenderId;
                    opts.name = objRoot["name"].toString();
                    opts.cloud = objRoot["cloud"].toString();

                    static const QRegularExpression re(rePortalName);
                    QRegularExpressionMatch match = re.match(opts.url);

                    if ( !_from_recovery && !match.hasMatch() ) {
                        QFileInfo _info(opts.url);
                        if ( /*!data->get_IsRecover() &&*/ !_info.exists() ) {
                            int res = CMessage::showMessage(m_appmanager.mainWindow()->handle(),
                                                            QObject::tr("%1 doesn't exists!<br>Remove file from the list?").arg(_info.fileName().toHtmlEscaped()),
                                                            MsgType::MSG_WARN, MsgBtns::mbYesDefNo);
                            if ( res == MODAL_RESULT_YES ) {
                                AscAppManager::sendCommandTo(SEND_TO_ALL_START_PAGE, "file:skip", QString::number(opts.id));
                            } else
                            if ( res == MODAL_RESULT_NO ) {
                                int uid = objRoot["hash"].toInt();
                                m_appmanager.onFileChecked(opts.name, uid, false);
                            }

                            return true;
                        }
                    }

                    openDocument(opts);
                }

                return true;
            } else
            if ( cmd.compare(L"recovery:update") == 0 ) {
                QJsonParseError jerror;
                QJsonDocument jdoc = QJsonDocument::fromJson(QString::fromStdWString(data.get_Param()).toUtf8(), &jerror);

                if( jerror.error == QJsonParseError::NoError ) {
                    if (jdoc.isArray()) {
                        const QJsonArray arr = jdoc.array();
                        for (const auto &val : arr) {
                            QJsonObject obj = val.toObject();
                            if (obj.contains("path")) {
                                QString path = obj["path"].toString();

                                COpenOptions opts{path.toStdWString(), etRecoveryFile, obj["id"].toInt()};
                                opts.parent_id = event.m_nSenderId;
                                opts.format = obj["type"].toInt();
                                opts.name = (QFileInfo(path)).fileName();
                                openDocument(opts);
                            }
                        }
                    }
                }

                return true;
            } else
            if ( cmd.compare(L"open:document") == 0 ) {
                const std::wstring & _url = data.get_Param();
                if ( !_url.empty() ) {
                    CCefView * _view = m_appmanager.GetViewByUrl(_url);
                    if ( _url.rfind(L"http://",0) == 0 || _url.rfind(L"https://",0) == 0 ) {
                        COpenOptions opts{_url};
                        opts.id = _view ? _view->GetId() : -1;
                    } else {
//                        /* open local file */
                    }
                }
            } else
            if ( cmd.compare(L"open:folder") == 0 ||
                    (!(cmd.find(L"editor:event") == std::wstring::npos) &&
                     !(data.get_Param().find(L"file:open") == std::wstring::npos)) )
            {
                std::wstring file_path = CEditorTools::getlocalfile(data.get_Param(), event.m_nSenderId).toStdWString();

                if ( !file_path.empty() ) {
                    QString qfile_path = QString::fromStdWString(file_path);
                    if ( bringEditorToFront(qfile_path) )
                        return true;

                    QFileInfo _info(qfile_path);
                    COpenOptions opts{_info.fileName(), etLocalFile};
                    opts.parent_id = event.m_nSenderId;
                    opts.url = qfile_path;
                    opts.wurl = file_path;

                    if ( !openDocument(opts) ) {
                        CMessage::error(m_appmanager.mainWindow()->handle(),
                                        QObject::tr("File %1 cannot be opened or doesn't exists.").arg(_info.fileName()));
                    }
                }

                return true;
            } else
            if ( cmd.compare(L"create:new") == 0 ) {
                const std::wstring & format = data.get_Param();
                const std::wstring search_tpl = L"template:";

                if ( format.rfind(search_tpl, 0) == 0 ) {
                    // a template picked on this computer
                    std::wstring type = format.substr(search_tpl.length());
                    const QString _path = CEditorTools::getlocaltemplate(type, event.m_nSenderId);
                    if ( !_path.isEmpty() )
                        createFromTemplate(_path, QString(), 0, event.m_nSenderId);
                } else if ( format.rfind(L"{\"template", 0) == 0 ) {
                    // a template of the gallery: only files of the template library
                    const QJsonObject obj = Utils::parseJsonString(format).value("template").toObject();
                    const QString _path = obj.value("path").toString();
                    if ( !CTemplateLibrary::isLibraryPath(_path) ) {
                        // pages can't open arbitrary files this way
                        return true;
                    }
                    createFromTemplate(_path, obj.value("app").toString(), obj.value("type").toInt(), event.m_nSenderId,
                                       obj.value("id").toString());
                } else {
                    int _f = format == L"word" ? AVS_OFFICESTUDIO_FILE_DOCUMENT_DOCX :
                                 format == L"cell" ? AVS_OFFICESTUDIO_FILE_SPREADSHEET_XLSX :
                                 format == L"form" ? AVS_OFFICESTUDIO_FILE_DOCUMENT_DOCXF :
                                 // format == L"draw" ? AVS_OFFICESTUDIO_FILE_DRAW_VSDX :
                                 format == L"slide" ? AVS_OFFICESTUDIO_FILE_PRESENTATION_PPTX : AVS_OFFICESTUDIO_FILE_UNKNOWN;

                    COpenOptions opts{m_appmanager.newFileName(_f), etNewFile};
                    opts.format = _f;
                    opts.parent_id = event.m_nSenderId;

                    openDocument(opts);
                }

                return true;
            }

        }
        }
        return false;
    }

    // New untitled document from a template. The template is checked first
    // (missing, damaged, wrong application, macros); the engine then converts
    // a copy of it, so saving the new document never writes to the template.
    auto createFromTemplate(const QString& path, const QString& app, int format, int sender,
                            const QString& id = QString()) -> bool
    {
        const CTemplateLibrary::Status st = CTemplateLibrary::validate(path, app);
        if ( st != CTemplateLibrary::Status::Ok ) {
            const QString name = QFileInfo(path).fileName();
            if ( !id.isEmpty() ) {
                // the page hides the card and says why
                const QJsonObject reply{{"id", id}, {"path", path}, {"status", CTemplateLibrary::statusName(st)}};
                m_appmanager.sendCommandTo(m_appmanager.GetViewById(sender), L"sos:templates:failed",
                                           Utils::stringifyJson(reply).toStdWString());
            }
            CMessage::error(m_appmanager.mainWindow() ? m_appmanager.mainWindow()->handle() : nullptr,
                            CTemplateLibrary::statusMessage(st, name));
            return false;
        }

        // the new document's kind comes from the checked file, not from the page
        const QString _app = CTemplateLibrary::appForTemplate(path);
        format = _app == "sheet" ? AVS_OFFICESTUDIO_FILE_SPREADSHEET_XLTX :
                 _app == "presentation" ? AVS_OFFICESTUDIO_FILE_PRESENTATION_POTX :
                 _app == "pdf" ? AVS_OFFICESTUDIO_FILE_DOCUMENT_OFORM_PDF : AVS_OFFICESTUDIO_FILE_DOCUMENT_DOTX;

        COpenOptions opts{m_appmanager.newFileName(format), etTemplateFile, path};
        opts.format = format;
        opts.parent_id = sender;

        // listed in the recent documents when it is first saved
        int view_id = -1;
        if ( openDocument(opts, &view_id) && view_id > -1 ) {
            CRecentDocuments::instance().expectTemplate(view_id, path);
            return true;
        }
        return false;
    }

    // Secure Office Suite template library: commands from start pages
    auto handleTemplatesCommand(const std::wstring& op, const std::wstring& param, int sender) -> void
    {
        const QJsonObject args = Utils::parseJsonString(param);
        CCefView * view = m_appmanager.GetViewById(sender);

        if ( op == L"check" ) {
            // statuses of the installed templates and the user's own templates
            const QJsonObject reply{
                {"status", CTemplateLibrary::check(args["items"].toArray())},
                {"user", CTemplateLibrary::scanUserFolder()},
                {"userFolder", QDir::toNativeSeparators(CTemplateLibrary::userFolder())},
            };
            m_appmanager.sendCommandTo(view, L"sos:templates:status", Utils::stringifyJson(reply).toStdWString());
        } else
        if ( op == L"folder" ) {
            if ( CTemplateLibrary::ensureUserFolder() )
                QDesktopServices::openUrl(QUrl::fromLocalFile(CTemplateLibrary::userFolder()));
        }
    }

    // Application of an editor: writer, sheet, presentation, pdf or empty
    auto appForView(int view_id) -> QString
    {
        CCefView * view = m_appmanager.GetViewById(view_id);
        if ( !view || view->GetType() != cvwtEditor )
            return QString();

        switch ( static_cast<CCefViewEditor *>(view)->GetEditorType() ) {
        case AscEditorType::etDocument:     return "writer";
        case AscEditorType::etSpreadsheet:  return "sheet";
        case AscEditorType::etPresentation: return "presentation";
        case AscEditorType::etPdf:
        case AscEditorType::etDocumentMasterForm: return "pdf";
        default: return QString();
        }
    }

    // Secure Office Suite File menu (Backstage) of the editors
    //  home        the editor's application start page
    //  templates   the application's templates for File > New
    //  about       product name, version and copyright for File > About
    //  exit        closes every window of the suite (unsaved documents ask first)
    auto handleBackstageCommand(const std::wstring& op, const std::wstring& param, int sender) -> void
    {
        const QJsonObject args = Utils::parseJsonString(param);
        CCefView * view = m_appmanager.GetViewById(sender);
        static const QStringList known{"writer", "sheet", "presentation", "pdf"};
        const QString view_app = appForView(sender),
                      page_app = known.contains(args["app"].toString()) ? args["app"].toString() : QString();

        if ( op == L"home" ) {
            // the start page of the kind of document in this window
            const QString app = view_app.isEmpty() ? page_app : view_app;
            if ( app.isEmpty() )
                CAscApplicationManagerWrapper::gotoMainWindow();
            else CAscApplicationManagerWrapper::showStartPage(app);
        } else
        if ( op == L"templates" ) {
            // the templates of the application whose menu asks
            const QString app = page_app.isEmpty() ? view_app : page_app;
            const QJsonObject reply{
                {"app", app},
                {"templates", app.isEmpty() ? QJsonArray() : CTemplateLibrary::templatesFor(app)},
                {"userFolder", QDir::toNativeSeparators(CTemplateLibrary::userFolder())},
            };
            m_appmanager.sendCommandTo(view, L"sos:backstage:templates", Utils::stringifyJson(reply).toStdWString());
        } else
        if ( op == L"about" ) {
            m_appmanager.sendCommandTo(view, L"sos:backstage:about",
                                       Utils::stringifyJson(CAscApplicationManagerWrapper::aboutInfo()).toStdWString());
        } else
        if ( op == L"exit" ) {
            QTimer::singleShot(0, &m_appmanager, [] {
                CAscApplicationManagerWrapper::closeAppWindows();
            });
        }
    }

    // Secure Office Suite recent documents: commands from start pages and editors
    auto handleRecentsCommand(const std::wstring& op, const std::wstring& param, int sender) -> void
    {
        CRecentDocuments & recents = CRecentDocuments::instance();
        const QJsonObject args = Utils::parseJsonString(param);
        const QString path = args["path"].toString();

        if ( op == L"get" ) {
            m_appmanager.sendCommandTo(m_appmanager.GetViewById(sender), L"sos:recents", recents.snapshotJson().toStdWString());
            recents.checkAvailability();
        } else
        if ( op == L"check" ) {
            recents.checkAvailability();
        } else
        if ( op == L"pin" ) {
            recents.setPinned(path, args["pinned"].toBool());
        } else
        if ( op == L"remove" ) {
            // only the list entry: the document itself stays where it is
            recents.remove(path);
        } else
        if ( op == L"clear" ) {
            recents.clear(args["app"].toString(), args["pinned"].toBool(false));
        } else
        if ( (op == L"open" || op == L"explore" || op == L"locate") && !recents.contains(path) ) {
            // pages may only open what the list holds
            return;
        } else
        if ( op == L"open" || op == L"explore" ) {
            const QString status = CRecentDocuments::checkPath(path);
            if ( status != "ok" ) {
                // the page offers to find the file or to remove it from the list
                const QJsonObject reply{{"path", path}, {"status", status}, {"action", QString::fromStdWString(op)}};
                m_appmanager.sendCommandTo(m_appmanager.GetViewById(sender), L"sos:recents:missing", Utils::stringifyJson(reply).toStdWString());
                recents.checkAvailability();
            } else
            if ( op == L"explore" ) {
                Utils::openFileLocation(path);
            } else {
                openRecentPath(path, sender);
            }
        } else
        if ( op == L"locate" ) {
            // a moved or renamed file: pick it, starting from the nearest folder that still exists
            QString folder = QFileInfo(path).absolutePath();
            while ( !folder.isEmpty() && !QDir(folder).exists() ) {
                const QString up = QFileInfo(folder).absolutePath();
                folder = up == folder ? QString() : up;
            }

            const QString app = CRecentDocuments::appForPath(path);
            const QString picked = CEditorTools::getlocalfile(QString("app:%1|%2").arg(app, folder).toStdWString(), sender);
            if ( !picked.isEmpty() ) {
                if ( !recents.relocate(path, picked) )
                    recents.registerDocument(picked, CRecentDocuments::Event::Opened);
                openRecentPath(picked, sender);
            }
        }
    }

    auto openRecentPath(const QString& path, int sender) -> void
    {
        if ( bringEditorToFront(path) )
            return;

        QFileInfo _info(path);
        COpenOptions opts{_info.fileName(), etLocalFile};
        opts.parent_id = sender;
        opts.url = path;
        opts.wurl = path.toStdWString();

        if ( !openDocument(opts) ) {
            CMessage::error(m_appmanager.mainWindow() ? m_appmanager.mainWindow()->handle() : nullptr,
                            QObject::tr("File %1 cannot be opened or doesn't exists.").arg(_info.fileName().toHtmlEscaped()));
        }
    }

    auto bringEditorToFront(int viewid) -> void
    {
        CEditorWindow * editor = m_appmanager.editorWindowFromViewId(viewid);
        if ( editor  ) {
            if (!editor->isSlideshowMode())
                editor->bringToTop();
        } else m_appmanager.mainWindow()->selectView(viewid);
    }

    auto bringEditorToFront(const QString& url) -> bool
    {
        CEditorWindow * _editor = nullptr;
        CCefView * _view = m_appmanager.GetViewByUrl(url.toStdWString());
        if ( _view ) {
            int _view_id = _view->GetId();

            if ( mainWindow() && (mainWindow()->slideshowHoldView(_view_id) || mainWindow()->holdUid(_view_id)) ) {
                if (!mainWindow()->isSlideshowMode()) {
                    mainWindow()->bringToTop();
                    mainWindow()->selectView(_view_id);
                }
                return true;
            } else
                _editor = m_appmanager.editorWindowFromViewId(_view_id);
        } else {
            QString _n_url = Utils::replaceBackslash(url);

            if ( mainWindow() && (mainWindow()->slideshowHoldUrl(_n_url, etLocalFile) || mainWindow()->holdUrl(_n_url, etLocalFile)) ) {
                if (!mainWindow()->isSlideshowMode()) {
                    mainWindow()->bringToTop();
                    mainWindow()->selectView(_n_url);
                }
                return true;
            } else {
                _editor = m_appmanager.editorWindowFromUrl(_n_url);
            }
        }

        if ( _editor ) {
            if (!_editor->isSlideshowMode())
                _editor->bringToTop();
            return true;
        }

        return false;
    }

    auto windowRectFromViewId(int viewid) -> QRect
    {
        if ( !(viewid < 0) ) {
            CEditorWindow * editor = m_appmanager.editorWindowFromViewId(viewid);
            if ( editor )
                return editor->normalGeometry();
            else
            if ( m_appmanager.mainWindow() && m_appmanager.mainWindow()->holdView(viewid) )
                return m_appmanager.mainWindow()->windowRect();
        }

        return QRect();
    }

    auto editorWindowGeometry(QRect &rc, bool &isMaximized, const COpenOptions& opts) -> void
    {        
        AscEditorType etype = AscEditorType::etUndefined;
        int format = (opts.format == 0) ? CCefViewEditor::GetFileFormat(opts.wurl) : opts.format;
        switch (format) {
        case AVS_OFFICESTUDIO_FILE_DOCUMENT_DOCXF:
            etype = AscEditorType::etPdf;
            break;
        default:
            etype = CEditorTools::editorTypeFromFormat(format);
            break;
        }

        if (!m_appmanager.m_vecEditors.empty()) {
#ifdef _WIN32
            if (HWND hWnd = GetTopWindow(GetDesktopWindow())) {
                do {
                    WId wid = (WId)hWnd;
#else
            std::vector<WId> winStack;
            LinuxWindowUtils::getWindowStack(winStack);
            if (winStack.empty()) {
                // Wayland fallback: use our tracked editors list
                for (auto it = m_appmanager.m_vecEditors.rbegin(); it != m_appmanager.m_vecEditors.rend(); it++) {
                    CEditorWindow *editor = reinterpret_cast<CEditorWindow*>(*it);
                    if (editor && editor->editorType() == etype) {
                        rc = editor->normalGeometry();
                        rc.adjust(50, 50, 50, 50);
                        isMaximized = editor->windowState().testFlag(Qt::WindowMaximized);
                        return;
                    }
                }
            }
            for (auto it = winStack.rbegin(); it != winStack.rend(); it++) {
                WId wid = (WId)(*it);
#endif
                    QWidget *wgt = QWidget::find(wid);
                    if (wgt && wgt->isWindow()) {
                        if (CEditorWindow *editor = qobject_cast<CEditorWindow*>(wgt)) {
                            if (editor->editorType() == etype) {
                                rc = editor->normalGeometry();
                                rc.adjust(50, 50, 50, 50);
                                isMaximized = editor->windowState().testFlag(Qt::WindowMaximized);
                                return;
                            }
                        }
                    }
#ifdef _WIN32
                } while ((hWnd = GetWindow(hWnd, GW_HWNDNEXT)) != nullptr);
            }
#else
            }
#endif
        }

        GET_REGISTRY_USER(reg_user);
        if (etype == AscEditorType::etUndefined) {
            if (!rc.isEmpty())
                rc.adjust(50,50,50,50);
            isMaximized = mainWindow() ? mainWindow()->windowState().testFlag(Qt::WindowMaximized) : reg_user.value("maximized", WindowHelper::defaultWindowMaximizeState()).toBool();
        } else {
            QString baseKey = "EditorsGeometry/" + QString::number(int(etype)) + "/";
            if (reg_user.contains(baseKey + "position"))
                rc = reg_user.value(baseKey + "position").toRect();
            else {
                if (!rc.isEmpty())
                    rc.adjust(50,50,50,50);
            }

            if (reg_user.contains(baseKey + "maximized"))
                isMaximized = reg_user.value(baseKey + "maximized").toBool();
            else {
                isMaximized = mainWindow() ? mainWindow()->windowState().testFlag(Qt::WindowMaximized) : reg_user.value("maximized", WindowHelper::defaultWindowMaximizeState()).toBool();
            }
        }
    }

    auto editorWindowFromViewId(int viewid) -> CEditorWindow *
    {
        return m_appmanager.editorWindowFromViewId(viewid);
    }

    auto openDocument(const COpenOptions& opts, int * view_id = nullptr) -> bool
    {
        // Each application only hosts its own documents: a spreadsheet
        // picked in Writer opens in SecureOffice Sheet, and so on.
        if ( routeToOwner(opts) ) {
            if ( view_id ) *view_id = -1;
            return true;
        }

        COpenOptions opts_ext{opts};
        if ( preferOpenEditorWindow() ) {
            GET_REGISTRY_USER(reg_user);
            bool isMaximized = false;
            QRect rect = /*isMaximized ? QRect() :*/ windowRectFromViewId(opts.parent_id);
            editorWindowGeometry(rect, isMaximized, opts);
            opts_ext.panel_size = CWindowBase::expectedContentSize(rect, true);
            opts_ext.parent_widget = COpenOptions::eWidgetType::window;
            if (CEditorWindow * editor_win = CEditorWindow::create(rect, opts_ext)) {
                editor_win->show(isMaximized);
                if ( view_id && editor_win->mainView() )
                    *view_id = editor_win->mainView()->cef()->GetId();

                m_appmanager.m_vecEditors.push_back(size_t(editor_win));
                if ( editor_win->isCustomWindowStyle() ) {
                    m_appmanager.sendCommandTo(editor_win->mainView()->cef(), L"window:features",
                                               Utils::stringifyJson(QJsonObject{{"skiptoparea", TOOLBTN_HEIGHT},{"singlewindow",true}}).toStdWString());
                }
                return true;
            }
        } else {
            m_appmanager.gotoMainWindow(size_t(m_appmanager.editorWindowFromViewId(opts.parent_id)));
            opts_ext.panel_size = mainWindow()->contentSize();
            opts_ext.parent_widget = COpenOptions::eWidgetType::tab;
            if (CTabPanel * panel = CEditorTools::createEditorPanel(opts_ext, mainWindow())) {
                if ( view_id )
                    *view_id = panel->cef()->GetId();
                CAscTabData * panel_data = panel->data();
                QRegularExpression re("^ascdesktop:\\/\\/(?:compare|merge|template)");
                if ( re.match(QString::fromStdWString(panel_data->url())).hasMatch() ) {
                    panel_data->setIsLocal(true);
                    panel_data->setUrl("");
                }
                mainWindow()->attachEditor(panel);
                return true;
            }
        }

        return false;

    }

    // true when the document belongs to another application and was
    // handed to it (cappidentity.h)
    auto routeToOwner(const COpenOptions& opts) -> bool
    {
        switch ( opts.srctype ) {
        case etLocalFile:
            return CAscApplicationManagerWrapper::routeLocalFile(opts.url.isEmpty() ? QString::fromStdWString(opts.wurl) : opts.url);
        case etRecentFile:
            if ( CFileInspector::isLocalFile(opts.url) && QFileInfo::exists(opts.url) )
                return CAscApplicationManagerWrapper::routeLocalFile(opts.url);
            return false;
        case etNewFile:
            return CAscApplicationManagerWrapper::routeNewDocument(opts.format);
        case etTemplateFile: {
            const QString path = QString::fromStdWString(opts.wurl);
            return CAscApplicationManagerWrapper::routeDocument(CTemplateLibrary::appForTemplate(path),
                                                               {"--sos-template=" + QDir::toNativeSeparators(path)});
        }
        default:
            return false;   // crash recovery stays with the application that saved it
        }
    }

#ifdef DOCUMENTSCORE_OPENSSL_SUPPORT
    auto selectSSLSertificate(int viewid) -> void {
        QWidget * parent = m_appmanager.editorWindowFromViewId(viewid);
        if ( !parent ) {
            parent = m_appmanager.mainWindowFromViewId(viewid);
        }

        if ( parent ) {
            CDialogOpenSsl _dialog(parent);

            NSEditorApi::CAscOpenSslData * pData = new NSEditorApi::CAscOpenSslData;
            if ( _dialog.exec() == QDialog::Accepted ) {
                _dialog.getResult(*pData);
            }

            NSEditorApi::CAscMenuEvent * pEvent = new NSEditorApi::CAscMenuEvent(ASC_MENU_EVENT_TYPE_PAGE_SELECT_OPENSSL_CERTIFICATE);
            pEvent->m_pData = pData;
            m_appmanager.GetViewById(viewid)->Apply(pEvent);
        }
    }
#endif

protected:
    auto mainWindow() -> CMainWindow * {
        return m_appmanager.m_pMainWindow;
    }

public:
    CAscApplicationManagerWrapper& m_appmanager;
    QPointer<QCefView> m_pStartPanel;
    bool m_openEditorWindow = false;
    bool m_needRestart = false;
    bool m_notificationSupported = false;
    std::shared_ptr<CPrintData> m_printData;
#ifndef _CAN_SCALE_IMMEDIATELY
    std::wstring uiscaling;
#endif
};

//CAscApplicationManagerWrapper::CAscApplicationManagerWrapper()
//    : CAscApplicationManagerWrapper(new CAscApplicationManagerWrapper::CAscApplicationManagerWrapper_Private(this))
//{
//}

#endif // CASCAPPLICATIONMANAGERWRAPPER_PRIVATE_H
