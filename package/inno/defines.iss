; -- CenOffice Desktop Editors Defines --

#define sCompanyName                    "CenOffice"
#define sIntCompanyName                 sCompanyName
#define sProductName                    "Desktop Editors"
#define sIntProductName                 "DesktopEditors"
#define sAppName                        str(sCompanyName)
#define sPackageName                    str(sIntCompanyName + "-" + sIntProductName)
#define sAppPublisher                   "CenOffice"
#define sAppPublisherURL                "https://github.com/workplace4cm"
#define sAppSupportURL                  "https://github.com/workplace4cm/DesktopEditors/issues"
#define sAppCopyright                   str("© Ascensio System SIA, Euro-Office contributors, CenOffice " + GetDateTimeString("yyyy",,) + ". All rights reserved.")
#define sAppIconName                    "CenOffice"
#define sOldAppIconName                 "CenOffice Editors"
#define sAppProtocol                    'oo-office'

#define APP_PATH                        str(sIntCompanyName + "\" + sIntProductName)
#define UPD_PATH                        str(sIntProductName + "Updates")
#define APP_REG_PATH                    str("Software\" + APP_PATH)
#define APP_REG_UNINST_KEY              str(sCompanyName + " " + sProductName)
#define APP_USER_MODEL_ID               "CenOffice.Documents.1"
#define APP_MUTEX_NAME                  "CenOffice"
#define APPWND_CLASS_NAME               "DocEditorsWindowClass"

#define iconsExe                        "DesktopEditors.exe"
#define NAME_EXE_OUT                    "editors.exe"

#define ASSC_APP_NAME                   "CenOffice"
#define ASCC_REG_PREFIX                 "ASC"
#define ASCC_REG_REGISTERED_APP_NAME    "CenOffice Editors"
#define ASSOC_PROG_ID                   "ASC.Editors"
#define ASSOC_APP_FRIENDLY_NAME         "CenOffice Editors"
