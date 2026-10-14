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

#include "cmainwindowimpl.h"
#include "cascapplicationmanagerwrapper.h"
#include "defines.h"
#include "utils.h"
#include "version.h"
#include "clangater.h"

#include <QJsonObject>
#include <QJsonDocument>
#include <QDir>
#include <QFile>


CMainWindowImpl::CMainWindowImpl(const QRect &rect) :
    CMainWindow(rect)
{
    QObject::connect(CLangater::getInstance(), &CLangater::onLangChanged, std::bind(&CMainWindowImpl::refreshAboutVersion, this));
}

void CMainWindowImpl::refreshAboutVersion()
{
    QJsonObject _json_obj;

    // About shows the product name, its own version and the copyright only:
    // no engine version, architecture, package type or license link.
    _json_obj["version"]    = ABOUT_VERSION_STR;

#if defined(ABOUT_PAGE_APP_NAME)
    _json_obj["appname"]    = ABOUT_PAGE_APP_NAME;
#else
    // _json_obj["appname"]    = WINDOW_NAME;
    _json_obj["appname"]    = "Secure Office Suite";
#endif
    _json_obj["rights"]     = ABOUT_COPYRIGHT_STR;
    _json_obj["link"]       = URL_SITE;
//    _json_obj["changelog"]  = "https://github.com/ONLYOFFICE/DesktopEditors/blob/master/CHANGELOG.md";

    AscAppManager::sendCommandTo(SEND_TO_ALL_START_PAGE, "app:version", Utils::stringifyJson(_json_obj));

    _json_obj.empty();
    _json_obj.insert("locale",
        QJsonObject({
            {"current", CLangater::getCurrentLangCode()},
            {"langs", CLangater::availableLangsToJson()}
        })
    );

//    if ( !AscAppManager::IsUseSystemScaling() ) {
        _json_obj["uiscaling"] = Scaling::factorToScaling(AscAppManager::userSettings(L"force-scale"));
//    }

#ifndef __OS_WIN_XP
    _json_obj["uitheme"] = QString::fromStdWString(GetCurrentTheme().id());
#endif

    _json_obj["spellcheckdetect"] = AscAppManager::userSettings(L"spell-check-input-mode") != L"0" ? "auto" : "off";

    GET_REGISTRY_USER(reg_user);
    _json_obj["editorwindowmode"] = reg_user.value("editorWindowMode",false).toBool();
    _json_obj["usegpu"] = !(AscAppManager::userSettings(L"disable-gpu") == L"1");
    _json_obj["useai"] = !(AscAppManager::userSettings(L"disable-ai") == L"1");

#ifndef __OS_WIN_XP
    _json_obj["rtl"] = AscAppManager::isRtlEnabled();
#endif

    // Read update settings
#ifdef _UPDMODULE
    if ( Utils::updatesAllowed() ) {
        AscAppManager::sendCommandTo(0, "updates:turn", "on");
        _json_obj["updates"] = QJsonObject({{"mode", reg_user.value("autoUpdateMode","ask").toString()}});
    }
#endif

    AscAppManager::sendCommandTo(SEND_TO_ALL_START_PAGE, "settings:init", Utils::stringifyJson(_json_obj));
    if ( InputArgs::contains(L"--ascdesktop-reveal-app-config") )
            AscAppManager::sendCommandTo( nullptr, "retrive:localoptions", "" );
}

void CMainWindowImpl::onLocalOptions(const QString& json)
{
    QJsonParseError jerror;
    QJsonDocument jdoc = QJsonDocument::fromJson(json.toLatin1(), &jerror);

    if( jerror.error == QJsonParseError::NoError ) {
        QFile file(Utils::getAppCommonPath() + "/app.conf");
        file.open(QFile::WriteOnly);
        file.write(jdoc.toJson());
        file.close();
    }
}

void CMainWindowImpl::doOpenLocalFile(COpenOptions& opts)
{
    CMainWindow::doOpenLocalFile(opts);
}

QString CMainWindowImpl::getSaveMessage() const
{
    return CMainWindow::getSaveMessage();
}

void CMainWindowImpl::onLocalFileSaveAs(void * d)
{
    Q_UNUSED(d)
}
