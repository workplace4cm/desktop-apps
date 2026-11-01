#!/bin/sh

set -e

# User data is never removed, not even on purge: settings, recent documents,
# templates and crash-recovery copies stay in each user's home folder
# (~/.config and ~/.local/share), so a later install finds them again.

MIMEAPPS=/etc/xdg/mimeapps.list
MARK="M4_PACKAGE_NAME default applications"
BEGIN="# BEGIN $MARK"
END="# END $MARK"

unset_default_apps() {
  [ -f "$MIMEAPPS" ] || return 0
  grep -qxF "$BEGIN" "$MIMEAPPS" || return 0
  tmp="$MIMEAPPS.dpkg-tmp"
  awk -v begin="$BEGIN" -v end="$END" '
    $0 == begin { skip = 1; next }
    $0 == end   { skip = 0; next }
    !skip
  ' "$MIMEAPPS" > "$tmp"
  # nothing left but the empty group the postinst created: remove the file
  if ! grep -v -e '^[[:space:]]*$' -e '^[[:space:]]*#' -e '^\[Default Applications\][[:space:]]*$' "$tmp" >/dev/null; then
    rm -f "$tmp" "$MIMEAPPS"
  else
    chmod 644 "$tmp"
    mv -f "$tmp" "$MIMEAPPS"
  fi
}

case "$1" in
  remove|purge)
    unset_default_apps
    rm -f /usr/share/mime/packages/onlyoffice-docxf.xml
    rm -f /usr/share/mime/packages/onlyoffice-oform.xml
  ;;

  upgrade)
    rm -f /usr/share/mime/packages/onlyoffice-docxf.xml
    rm -f /usr/share/mime/packages/onlyoffice-oform.xml
  ;;

  failed-upgrade|abort-install|abort-upgrade|disappear)
  ;;

  *)
    echo "postrm called with unknown argument \`$1'" >&2
    exit 1
  ;;
esac

#DEBHELPER#

exit 0
