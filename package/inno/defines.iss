; -- Secure Office Suite Defines --

#define sCompanyName                    "Secure Office Suite"
#define sIntCompanyName                 sCompanyName
#define sProductName                    "Desktop Editors"
#define sIntProductName                 "DesktopEditors"
#define sAppName                        str(sCompanyName)
#define sPackageName                    str(sIntCompanyName + "-" + sIntProductName)
#define sAppPublisher                   "Secure Office Suite"
#define sAppPublisherURL                ""
#define sAppSupportURL                  ""
#define sAppCopyright                   str("© Secure Office Suite " + GetDateTimeString("yyyy",,) + ". Portions © Ascensio System SIA.")
#define sAppIconName                    "Secure Office Suite"
#define sOldAppIconName                 "Secure Office Suite Editors"
#define sAppProtocol                    'oo-office'

#define APP_PATH                        str(sIntCompanyName + "\" + sIntProductName)
#define UPD_PATH                        str(sIntProductName + "Updates")
#define APP_REG_PATH                    str("Software\" + APP_PATH)
#define APP_REG_UNINST_KEY              str(sCompanyName + " " + sProductName)
#define APP_USER_MODEL_ID               "SecureOfficeSuite.Documents.1"
#define APP_MUTEX_NAME                  "SecureOfficeSuite"
#define APPWND_CLASS_NAME               "DocEditorsWindowClass"

#define iconsExe                        "DesktopEditors.exe"
#define NAME_EXE_OUT                    "editors.exe"

#define ASSC_APP_NAME                   "Secure Office Suite"
#define ASCC_REG_PREFIX                 "ASC"
#define ASCC_REG_REGISTERED_APP_NAME    "Secure Office Suite"
#define ASSOC_PROG_ID                   "ASC.Editors"
#define ASSOC_APP_FRIENDLY_NAME         "Secure Office Suite"
