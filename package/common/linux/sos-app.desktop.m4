include(defines.m4)dnl
dnl Secure Office Suite application launcher: m4 -D M4_SOS_APP=writer|sheet|presentation|pdf
dnl Each application opens on its own start page; a file passed by the file
dnl manager opens directly.
[Desktop Entry]
Version=1.0
Type=Application
ifelse(M4_SOS_APP,`writer',`dnl
Name=EuroOffice Writer
GenericName=Word Processor
Comment=Create and edit text documents
Icon=x-office-document
Keywords=Text;Document;Letter;Report;odt;doc;docx;rtf;txt;
Categories=Office;WordProcessor;
MimeType=application/msword;application/vnd.openxmlformats-officedocument.wordprocessingml.document;application/vnd.openxmlformats-officedocument.wordprocessingml.template;application/vnd.ms-word.document.macroEnabled.12;application/vnd.oasis.opendocument.text;application/vnd.oasis.opendocument.text-template;application/rtf;text/plain;
',M4_SOS_APP,`sheet',`dnl
Name=EuroOffice Sheet
GenericName=Spreadsheet
Comment=Create and edit spreadsheets
Icon=x-office-spreadsheet
Keywords=Spreadsheet;Workbook;Table;xls;xlsx;ods;csv;
Categories=Office;Spreadsheet;
MimeType=application/vnd.ms-excel;application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;application/vnd.openxmlformats-officedocument.spreadsheetml.template;application/vnd.ms-excel.sheet.macroEnabled.12;application/vnd.oasis.opendocument.spreadsheet;application/vnd.oasis.opendocument.spreadsheet-template;text/csv;
',M4_SOS_APP,`presentation',`dnl
Name=EuroOffice Presentation
GenericName=Presentation
Comment=Create and edit presentations
Icon=x-office-presentation
Keywords=Presentation;Slides;ppt;pptx;odp;
Categories=Office;Presentation;
MimeType=application/vnd.ms-powerpoint;application/vnd.openxmlformats-officedocument.presentationml.presentation;application/vnd.openxmlformats-officedocument.presentationml.template;application/vnd.openxmlformats-officedocument.presentationml.slideshow;application/vnd.oasis.opendocument.presentation;application/vnd.oasis.opendocument.presentation-template;
',`dnl
Name=EuroOffice PDF
GenericName=PDF Viewer
Comment=View, fill in and annotate PDF documents
Icon=application-pdf
Keywords=PDF;Form;Viewer;
Categories=Office;Viewer;
MimeType=application/pdf;
')dnl
Exec=/usr/bin/M4_DESKTOPEDITORS_EXEC --app=M4_SOS_APP %F
Terminal=false
StartupWMClass=_WM_CLASS
