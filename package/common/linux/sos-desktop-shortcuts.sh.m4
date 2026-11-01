#!/bin/sh
dnl Secure Office Suite: desktop shortcuts for the four applications.
dnl Ubuntu puts applications in the app grid and the dock, not on the desktop,
dnl so the package doesn't; a user (or an administrator, per user) runs this.
# Puts EuroOffice Writer, Sheet, Presentation and PDF on your desktop.
# Run it without arguments to add the four shortcuts, with --remove to take
# them away again.
set -e

desktop=$(xdg-user-dir DESKTOP 2>/dev/null || true)
if [ -z "$desktop" ] || [ "$desktop" = "$HOME" ]; then
  desktop=$HOME/Desktop
fi

for app in writer sheet presentation pdf; do
  src=/usr/share/applications/M4_DESKTOPEDITORS_EXEC-$app.desktop
  dst=$desktop/M4_DESKTOPEDITORS_EXEC-$app.desktop
  if [ "$1" = "--remove" ]; then
    rm -f "$dst"
    continue
  fi
  mkdir -p "$desktop"
  cp -f "$src" "$dst"
  chmod 755 "$dst"
  # GNOME's desktop launches a shortcut only when it is marked trusted
  gio set "$dst" metadata::trusted true 2>/dev/null || true
  echo "$dst"
done
