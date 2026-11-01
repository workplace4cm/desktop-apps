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

#include <windowsx.h>
#include "cascapplicationmanagerwrapper.h"
#include "singleapplication.h"
#include "defines.h"
#include "cappidentity.h"
#include <QThread>

// Each application (Writer, Sheet, Presentation, PDF) is its own single
// instance: its own mutex and its own message window.
#define RECEIVER_WINDOW receiverClass().c_str()

static std::wstring receiverClass()
{
    static const std::wstring cls = AppIdentity::receiverClass(QString::fromWCharArray(WINDOW_CLASS_NAME)).toStdWString();
    return cls;
}
#define RETRIES_COUNT 10
#define RETRIES_DELAY_MS 500


SingleApplication::SingleApplication(int &argc, char *argv[]) :
    QApplication(argc, argv),
    m_isPrimary(false)
{
    m_hMutex = CreateMutex(NULL, FALSE, AppIdentity::lockName(QString::fromUtf8(APP_MUTEX_NAME)).toStdWString().c_str());
    if (GetLastError() != ERROR_ALREADY_EXISTS) {
        m_isPrimary = true;
        startPrimary();
    }
}

SingleApplication::~SingleApplication()
{
    if (m_isPrimary && m_hMutex != nullptr)
        CloseHandle(m_hMutex);

    if (m_hWnd)
        DestroyWindow(m_hWnd);
}

bool SingleApplication::isPrimary() const
{
    return m_isPrimary;
}

bool SingleApplication::sendMessage(const QByteArray &message)
{
    if (m_isPrimary)
        return false;

    HWND hwnd = NULL;
    int retries = RETRIES_COUNT;
    do {
        QThread::msleep(RETRIES_DELAY_MS);
        hwnd = FindWindowEx(HWND_MESSAGE, NULL, RECEIVER_WINDOW, NULL);
        if (hwnd == NULL)
            hwnd = FindWindow(RECEIVER_WINDOW, NULL);
    } while (retries-- > 0 && hwnd == NULL);

    if (hwnd != NULL) {
        QString msg(message);
        wchar_t *cm_line = new wchar_t[msg.length() + 1];
        msg.toWCharArray(cm_line);
        cm_line[msg.length()] = '\0';

        // the running application may come to the front with the document
        // (EuroOffice Writer, Sheet... hand documents to each other)
        AllowSetForegroundWindow(ASFW_ANY);

        COPYDATASTRUCT MyCDS = {1};
        MyCDS.cbData = sizeof(WCHAR) * (wcslen(cm_line) + 1);
        MyCDS.lpData = cm_line;
        SendMessage(hwnd, WM_COPYDATA, WPARAM(0), LPARAM((LPVOID)&MyCDS));
        delete[] cm_line;
        return true;
    }
    return false;
}

void SingleApplication::startPrimary()
{
    HINSTANCE hInstance = GetModuleHandle(nullptr);
    WNDCLASSEX wcx{sizeof(WNDCLASSEX)};
    wcx.hInstance = hInstance;
    wcx.lpfnWndProc = WndProc;
    wcx.lpszClassName = RECEIVER_WINDOW;
    RegisterClassEx(&wcx);

    m_hWnd = CreateWindowEx(0, RECEIVER_WINDOW, nullptr, 0, 0, 0, 0, 0, HWND_MESSAGE, nullptr, hInstance, nullptr);
    SetWindowLongPtr(m_hWnd, GWLP_USERDATA, reinterpret_cast<LONG_PTR>(this));
}

void SingleApplication::invokeSignal(const QString &data)
{
    emit receivedMessage(data.toUtf8());
}

LRESULT SingleApplication::WndProc(HWND hWnd, UINT msg, WPARAM wParam, LPARAM lParam)
{
    SingleApplication *app = reinterpret_cast<SingleApplication*>(GetWindowLongPtr(hWnd, GWLP_USERDATA));
    if (!app)
        return DefWindowProc(hWnd, msg, wParam, lParam);

    switch (msg) {
    case WM_COPYDATA: {
        COPYDATASTRUCT* pcds = (COPYDATASTRUCT*)lParam;
        if (pcds->dwData == 1 && pcds->lpData)
            QMetaObject::invokeMethod(app, "invokeSignal", Qt::QueuedConnection, Q_ARG(QString, QString::fromWCharArray((WCHAR*)pcds->lpData)));
        break;
    }
    case UM_INSTALL_UPDATE: {
        QTimer::singleShot(500, []() {
            AscAppManager::closeAppWindows();
        });
        break;
    }
    default:
        break;
    }
    return DefWindowProc(hWnd, msg, wParam, lParam);
}
