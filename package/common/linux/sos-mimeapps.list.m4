include(defines.m4)dnl
dnl Secure Office Suite: the file types EuroOffice Writer, Sheet, Presentation
dnl and PDF open by default. The package's postinst copies these lines into
dnl the system-wide /etc/xdg/mimeapps.list (between BEGIN/END markers that
dnl postrm removes again); a user's own choice in ~/.config/mimeapps.list
dnl still wins. Each application's .desktop lists further types it can open.
define(`W', `$1=M4_DESKTOPEDITORS_EXEC-writer.desktop')dnl
define(`S', `$1=M4_DESKTOPEDITORS_EXEC-sheet.desktop')dnl
define(`P', `$1=M4_DESKTOPEDITORS_EXEC-presentation.desktop')dnl
define(`F', `$1=M4_DESKTOPEDITORS_EXEC-pdf.desktop')dnl
W(application/msword)
W(application/msword-template)
W(application/vnd.ms-word.document.macroEnabled.12)
W(application/vnd.ms-word.template.macroEnabled.12)
W(application/vnd.openxmlformats-officedocument.wordprocessingml.document)
W(application/vnd.openxmlformats-officedocument.wordprocessingml.template)
W(application/vnd.oasis.opendocument.text)
W(application/vnd.oasis.opendocument.text-flat-xml)
W(application/vnd.oasis.opendocument.text-template)
W(application/rtf)
W(text/rtf)
W(text/plain)
S(application/vnd.ms-excel)
S(application/vnd.ms-excel.sheet.macroEnabled.12)
S(application/vnd.ms-excel.sheet.binary.macroEnabled.12)
S(application/vnd.ms-excel.template.macroEnabled.12)
S(application/vnd.openxmlformats-officedocument.spreadsheetml.sheet)
S(application/vnd.openxmlformats-officedocument.spreadsheetml.template)
S(application/vnd.oasis.opendocument.spreadsheet)
S(application/vnd.oasis.opendocument.spreadsheet-flat-xml)
S(application/vnd.oasis.opendocument.spreadsheet-template)
S(text/csv)
P(application/vnd.ms-powerpoint)
P(application/vnd.ms-powerpoint.presentation.macroEnabled.12)
P(application/vnd.ms-powerpoint.slideshow.macroEnabled.12)
P(application/vnd.ms-powerpoint.template.macroEnabled.12)
P(application/vnd.openxmlformats-officedocument.presentationml.presentation)
P(application/vnd.openxmlformats-officedocument.presentationml.slideshow)
P(application/vnd.openxmlformats-officedocument.presentationml.template)
P(application/vnd.oasis.opendocument.presentation)
P(application/vnd.oasis.opendocument.presentation-flat-xml)
P(application/vnd.oasis.opendocument.presentation-template)
F(application/pdf)
