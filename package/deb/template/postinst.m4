#!/bin/sh
# EuroOffice Writer, Sheet, Presentation and PDF become the system-wide
# default applications for their file types: the package's list is copied
# into /etc/xdg/mimeapps.list between two marker lines (postrm removes them).
# Settings a user made in ~/.config/mimeapps.list still win, and lines an
# administrator wrote outside the markers are kept and win too.

set -e

MIMEAPPS=/etc/xdg/mimeapps.list
DEFAULTS=/usr/share/M4_PACKAGE_NAME/mimeapps.list
MARK="M4_PACKAGE_NAME default applications"
BEGIN="# BEGIN $MARK"
END="# END $MARK"

set_default_apps() {
  [ -f "$DEFAULTS" ] || return 0
  mkdir -p "$(dirname "$MIMEAPPS")"
  [ -f "$MIMEAPPS" ] || printf '[Default Applications]\n' > "$MIMEAPPS"
  tmp="$MIMEAPPS.dpkg-tmp"
  # drop the old block, then put the new one right after the group header
  # (or start the group): later lines of the group override it
  awk -v begin="$BEGIN" -v end="$END" -v defaults="$DEFAULTS" '
    function block() {
      print begin
      while ((getline line < defaults) > 0) print line
      close(defaults)
      print end
      done = 1
    }
    $0 == begin { skip = 1; next }
    $0 == end   { skip = 0; next }
    skip        { next }
    { print }
    /^\[Default Applications\][ \t]*$/ && !done { block() }
    END { if (!done) { print ""; print "[Default Applications]"; block() } }
  ' "$MIMEAPPS" > "$tmp"
  chmod 644 "$tmp"
  mv -f "$tmp" "$MIMEAPPS"
}

case "$1" in
  configure)
    set_default_apps
    # menus and file managers pick up the applications and their file types
    if command -v update-desktop-database >/dev/null 2>&1; then
      update-desktop-database -q /usr/share/applications || true
    fi
    if command -v gtk-update-icon-cache >/dev/null 2>&1; then
      gtk-update-icon-cache -q -t -f /usr/share/icons/hicolor || true
    fi
  ;;

  abort-upgrade|abort-remove|abort-deconfigure)
  ;;

  *)
    echo "postinst called with unknown argument \`$1'" >&2
    exit 1
  ;;
esac

#DEBHELPER#

exit 0
