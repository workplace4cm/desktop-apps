include(defines.m4)dnl
dnl Secure Office Suite application launcher: m4 -D M4_SOS_APP=writer|sheet|presentation|pdf
dnl Each application is its own program for the desktop: its own command,
dnl icon, window class (StartupWMClass = the application's name, which is
dnl its X11 WM_CLASS; on Wayland the window's app_id is this file's name),
dnl start page and file types. A file passed by the file manager opens
dnl directly in it.
[Desktop Entry]
Version=1.0
Type=Application
ifelse(M4_SOS_APP,`writer',`dnl
Name=SecureOffice Writer
GenericName=Word Processor
Comment=Create and edit text documents
Keywords=Text;Document;Letter;Report;odt;doc;docx;rtf;txt;
Categories=Office;WordProcessor;
MimeType=application/msword;application/msword-template;application/vnd.ms-word.document.macroEnabled.12;application/vnd.ms-word.template.macroEnabled.12;application/vnd.openxmlformats-officedocument.wordprocessingml.document;application/vnd.openxmlformats-officedocument.wordprocessingml.template;application/vnd.oasis.opendocument.text;application/vnd.oasis.opendocument.text-flat-xml;application/vnd.oasis.opendocument.text-template;application/vnd.sun.xml.writer;application/vnd.sun.xml.writer.template;application/vnd.apple.pages;application/wps-office.wps;application/wps-office.wpt;application/x-hwp;application/epub+zip;application/x-fictionbook+xml;application/rtf;text/rtf;text/markdown;text/plain;
StartupWMClass=SecureOffice Writer
',M4_SOS_APP,`sheet',`dnl
Name=SecureOffice Sheet
GenericName=Spreadsheet
Comment=Create and edit spreadsheets
Keywords=Spreadsheet;Workbook;Table;xls;xlsx;ods;csv;
Categories=Office;Spreadsheet;
MimeType=application/vnd.ms-excel;application/vnd.ms-excel.sheet.macroEnabled.12;application/vnd.ms-excel.sheet.binary.macroEnabled.12;application/vnd.ms-excel.template.macroEnabled.12;application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;application/vnd.openxmlformats-officedocument.spreadsheetml.template;application/vnd.oasis.opendocument.spreadsheet;application/vnd.oasis.opendocument.spreadsheet-flat-xml;application/vnd.oasis.opendocument.spreadsheet-template;application/vnd.sun.xml.calc;application/vnd.apple.numbers;application/wps-office.et;application/wps-office.ett;text/csv;text/tab-separated-values;
StartupWMClass=SecureOffice Sheet
',M4_SOS_APP,`presentation',`dnl
Name=SecureOffice Presentation
GenericName=Presentation
Comment=Create and edit presentations
Keywords=Presentation;Slides;ppt;pptx;odp;
Categories=Office;Presentation;
MimeType=application/vnd.ms-powerpoint;application/vnd.ms-powerpoint.presentation.macroEnabled.12;application/vnd.ms-powerpoint.slideshow.macroEnabled.12;application/vnd.ms-powerpoint.template.macroEnabled.12;application/vnd.openxmlformats-officedocument.presentationml.presentation;application/vnd.openxmlformats-officedocument.presentationml.slideshow;application/vnd.openxmlformats-officedocument.presentationml.template;application/vnd.oasis.opendocument.presentation;application/vnd.oasis.opendocument.presentation-flat-xml;application/vnd.oasis.opendocument.presentation-template;application/vnd.oasis.opendocument.graphics;application/vnd.sun.xml.impress;application/vnd.apple.keynote;application/wps-office.dps;application/wps-office.dpt;
StartupWMClass=SecureOffice Presentation
',`dnl
Name=SecureOffice PDF
GenericName=PDF Editor
Comment=View, fill in, annotate and edit PDF documents
Keywords=PDF;Form;Viewer;Annotate;xps;djvu;
Categories=Office;Viewer;
MimeType=application/pdf;application/vnd.ms-xpsdocument;application/oxps;image/vnd.djvu;
StartupWMClass=SecureOffice PDF
')dnl
Icon=M4_DESKTOPEDITORS_EXEC-M4_SOS_APP
TryExec=/usr/bin/M4_DESKTOPEDITORS_EXEC-M4_SOS_APP
Exec=/usr/bin/M4_DESKTOPEDITORS_EXEC-M4_SOS_APP %F
Terminal=false
Actions=New;

[Desktop Action New]
ifelse(M4_SOS_APP,`writer',`dnl
Name=New document
Exec=/usr/bin/M4_DESKTOPEDITORS_EXEC-M4_SOS_APP --new:word
',M4_SOS_APP,`sheet',`dnl
Name=New spreadsheet
Exec=/usr/bin/M4_DESKTOPEDITORS_EXEC-M4_SOS_APP --new:cell
',M4_SOS_APP,`presentation',`dnl
Name=New presentation
Exec=/usr/bin/M4_DESKTOPEDITORS_EXEC-M4_SOS_APP --new:slide
',`dnl
Name=New PDF form
Exec=/usr/bin/M4_DESKTOPEDITORS_EXEC-M4_SOS_APP --new:form
')dnl
