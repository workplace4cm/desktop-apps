#!/bin/sh
dnl Secure Office Suite application command: m4 -D M4_SOS_APP=writer|sheet|presentation|pdf
dnl Starts the application on its start page, or opens the documents given.
exec /usr/bin/M4_DESKTOPEDITORS_EXEC --app=M4_SOS_APP "$@"
