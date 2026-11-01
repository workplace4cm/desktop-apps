#!/bin/bash
# Secure Office Suite: Ubuntu integration of EuroOffice Writer, Sheet,
# Presentation and PDF, checked on the installed package.
#
#   verify_integration.sh <prefix> <deb> <out-dir>
#     prefix   installed command prefix, e.g. secure-office-suite-desktopeditors
#     deb      the package file that is installed (used to build an upgrade)
#     out-dir  where screenshots and logs go
#
# Needs an X server on $DISPLAY with a window manager, xdotool, xprop, gio
# (libglib2.0-bin), desktop-file-utils and sudo. Checks:
#   1. four application entries in the menus (the suite entry is hidden),
#      each with its own icon, and every launcher starts its application;
#   2. each file type's default application, as the file manager asks for it
#      (gio), and a "double-click" (gio open) on a document of each type
#      opens that very document in the right application;
#   3. the desktop-shortcuts command;
#   4. an upgrade keeps settings, recent documents, recovery copies and
#      documents, and the default applications;
#   5. remove and purge take the applications, menu entries and default
#      applications away but leave user data and documents alone.

set -u
PREFIX=${1:?prefix}
DEB=$(readlink -f "${2:?deb}")
OUT=${3:?out dir}
mkdir -p "$OUT"
HERE=$(cd "$(dirname "$0")" && pwd)
FAILS=0
PKG=$(dpkg-deb -f "$DEB" Package)
BASE=$(echo "$PREFIX" | sed 's/-desktopeditors$//')
APP_DIR=/opt/$BASE/desktopeditors
DATA=$HOME/.local/share/$BASE/desktopeditors
CONF=$HOME/.config/$BASE
DOCS=$HOME/Documents/sos-integration
MIMEAPPS=/etc/xdg/mimeapps.list
APPS="writer sheet presentation pdf"

ok()   { echo "PASS: $*"; }
fail() { echo "FAIL: $*"; FAILS=$((FAILS + 1)); }
shot() { import -window root "$OUT/$1.png" 2>/dev/null || true; }

app_name() {
    case $1 in
        writer) echo "EuroOffice Writer";; sheet) echo "EuroOffice Sheet";;
        presentation) echo "EuroOffice Presentation";; pdf) echo "EuroOffice PDF";;
    esac
}

# the application a sample document belongs to
owner() {
    case ${1##*.} in
        doc|docx|odt|rtf|txt) echo writer;;
        xls|xlsx|ods|csv) echo sheet;;
        ppt|pptx|odp) echo presentation;;
        pdf) echo pdf;;
    esac
}

# pid of the first window whose title matches the regex $1 (fails after $2 s)
wait_window() {
    local re=$1 secs=${2:-150} w
    for _ in $(seq "$secs"); do
        w=$(xdotool search --onlyvisible --name "$re" 2>/dev/null | head -1)
        if [ -n "$w" ]; then
            xdotool getwindowpid "$w" 2>/dev/null || echo "?"
            return 0
        fi
        sleep 1
    done
    return 1
}

app_of_pid() {   # the --app=<id> a process runs as
    tr '\0' '\n' < "/proc/$1/cmdline" 2>/dev/null | sed -n 's/^--app=//p' | head -1
}

close_apps() {
    pkill -u "$(id -u)" -f -- "$APP_DIR/DesktopEditors" 2>/dev/null
    for _ in $(seq 30); do
        pgrep -u "$(id -u)" -f -- "$APP_DIR/DesktopEditors" >/dev/null || return 0
        sleep 1
    done
    pkill -9 -u "$(id -u)" -f -- "$APP_DIR/DesktopEditors" 2>/dev/null
    sleep 2
}

titles() {
    for w in $(xdotool search --onlyvisible --name '.' 2>/dev/null); do xdotool getwindowname "$w"; done | sort -u
}

# a document opens in its own application; $1 = file, $2 = how it was opened
expect_document() {
    local f=$1 how=$2 app name re pid got
    app=$(owner "$f"); name=$(app_name "$app")
    re="^\*?$(basename "$f" | sed 's/\./\\./g')( .*)? - $name\$"
    if pid=$(wait_window "$re" 150); then
        got=$(app_of_pid "$pid")
        [ "$got" = "$app" ] && ok "$(basename "$f") ($how) opened in $name (pid $pid)" \
                            || fail "$(basename "$f") ($how) window is in pid $pid running '--app=$got'"
    else
        fail "$(basename "$f") ($how) did not open in $name"
        titles | sed 's/^/    window: /'
    fi
}

mkdir -p "$DOCS"
cp "$HERE"/samples/Sample.* "$DOCS/"
close_apps

# -- 1. menu entries, icons and launchers
echo "== menu entries"
visible=()
for f in /usr/share/applications/"$PREFIX"*.desktop; do
    desktop-file-validate "$f" || fail "$f does not validate"
    if grep -qx 'NoDisplay=true' "$f"; then
        echo "hidden: $(basename "$f")"
    else
        visible+=("$(basename "$f" .desktop)")
    fi
done
expected=$(for a in $APPS; do echo "$PREFIX-$a"; done | sort)
actual=$(printf '%s\n' "${visible[@]}" | sort)
[ "$actual" = "$expected" ] && ok "the menus show exactly the four applications: ${visible[*]}" \
                            || fail "menu entries: ${visible[*]}"
for app in $APPS; do
    f=/usr/share/applications/$PREFIX-$app.desktop
    name=$(app_name "$app")
    grep -qx "Name=$name" "$f" && ok "$f is named $name" || fail "$f is not named $name"
    grep -q '^Categories=.*Office;' "$f" && ok "$app is in the Office menu" || fail "$app is not in the Office menu"
    icon=$(sed -n 's/^Icon=//p' "$f")
    missing=""
    for s in 16x16 24x24 32x32 48x48 64x64 128x128 256x256; do
        [ -f "/usr/share/icons/hicolor/$s/apps/$icon.png" ] || missing="$missing $s"
    done
    [ -f "/usr/share/icons/hicolor/scalable/apps/$icon.svg" ] || missing="$missing scalable"
    [ -z "$missing" ] && ok "$app has its own icon $icon in every size" || fail "$app icon $icon missing:$missing"
done
for app in $APPS; do
    name=$(app_name "$app")
    gio launch "/usr/share/applications/$PREFIX-$app.desktop" >>"$OUT/launch.log" 2>&1 &
    if pid=$(wait_window "^$name\$" 150); then
        [ "$(app_of_pid "$pid")" = "$app" ] && ok "the $name menu entry starts $name (pid $pid)" \
                                             || fail "the $name menu entry started pid $pid ($(app_of_pid "$pid"))"
    else
        fail "the $name menu entry did not start $name"
    fi
done
shot 1-launchers
close_apps

# -- 2. file types: default application and double-click
echo "== file types"
grep -c "^# BEGIN .*default applications" "$MIMEAPPS" | grep -qx 1 && ok "$MIMEAPPS has the default applications once" \
                                                                    || fail "$MIMEAPPS: $(cat "$MIMEAPPS" 2>/dev/null | head -3)"
for f in "$DOCS"/Sample.*; do
    app=$(owner "$f")
    mime=$(gio info -a standard::content-type "$f" | sed -n 's/.*standard::content-type: //p')
    def=$(gio mime "$mime" 2>/dev/null | sed -n 's/^Default application for .*: //p')
    [ "$def" = "$PREFIX-$app.desktop" ] && ok "$(basename "$f") ($mime) opens with $def" \
                                        || fail "$(basename "$f") ($mime) opens with '$def', expected $PREFIX-$app.desktop"
    xdg=$(xdg-mime query default "$mime" 2>/dev/null)
    [ "$xdg" = "$PREFIX-$app.desktop" ] && ok "xdg-mime agrees for $mime" || fail "xdg-mime: $mime -> '$xdg'"
done
for f in "$DOCS"/Sample.*; do
    gio open "$f" >>"$OUT/gio-open.log" 2>&1
    expect_document "$f" "double-click"
done
shot 2-double-click
titles > "$OUT/titles-double-click.txt"
for app in $APPS; do
    n=$(pgrep -u "$(id -u)" -f -- "$APP_DIR/DesktopEditors --app=$app" | wc -l)
    [ "$n" = 1 ] && ok "one $app process for all its documents" || fail "$n $app processes"
done
close_apps

# -- 3. desktop shortcuts
echo "== desktop shortcuts"
desk=$(xdg-user-dir DESKTOP 2>/dev/null); { [ -z "$desk" ] || [ "$desk" = "$HOME" ]; } && desk=$HOME/Desktop
"$PREFIX-desktop-shortcuts" > "$OUT/shortcuts.log" 2>&1 || fail "$PREFIX-desktop-shortcuts failed"
for app in $APPS; do
    s=$desk/$PREFIX-$app.desktop
    [ -x "$s" ] && desktop-file-validate "$s" && ok "desktop shortcut for $app" || fail "no desktop shortcut $s"
done
"$PREFIX-desktop-shortcuts" --remove >> "$OUT/shortcuts.log" 2>&1
ls "$desk"/"$PREFIX"-*.desktop >/dev/null 2>&1 && fail "--remove left shortcuts" || ok "--remove took the shortcuts away"

# -- 4. upgrade keeps user data
echo "== upgrade"
mkdir -p "$DATA" "$CONF"
echo "user data $(date)" > "$DATA/sos-integration-marker"
echo "settings $(date)" > "$CONF/sos-integration-marker"
snapshot() {   # user files that must survive, with checksums (browser caches excluded)
    { find "$DATA" "$CONF" -type f ! -path '*/cache*' ! -name '*.lock' ! -name 'LOCK' 2>/dev/null
      find "$DOCS" -type f; } | sort | xargs -r -d '\n' sha256sum
}
snapshot > "$OUT/user-files-before.txt"
echo "user files: $(wc -l < "$OUT/user-files-before.txt")"
grep -q "recents.xml" "$OUT/user-files-before.txt" && ok "recent documents were recorded" || echo "note: no recents.xml yet"
grep -q "/recover-" <(find "$DATA" -type d) && ok "recovery folders exist before the upgrade" || echo "note: no recovery folders"
find "$DATA" -maxdepth 2 -type d -name 'recover*' | sort > "$OUT/recover-before.txt"

work=$(mktemp -d)
# the same package one version later (as root, so the files stay root's)
sudo dpkg-deb -R "$DEB" "$work/pkg"
v=$(dpkg-deb -f "$DEB" Version)
sudo sed -i "s/^Version: .*/Version: $v+upgrade1/" "$work/pkg/DEBIAN/control"
sudo dpkg-deb -Zxz -z1 -b "$work/pkg" "$work/upgrade.deb" >/dev/null
sudo rm -rf "$work/pkg"
if sudo apt-get install -y -qq "$work/upgrade.deb" > "$OUT/upgrade.log" 2>&1; then
    [ "$(dpkg-query -W -f '${Version}' "$PKG")" = "$v+upgrade1" ] && ok "upgraded $PKG $v -> $v+upgrade1" || fail "version after upgrade: $(dpkg-query -W -f '${Version}' "$PKG")"
else
    fail "upgrade failed"; tail -20 "$OUT/upgrade.log"
fi
snapshot > "$OUT/user-files-after-upgrade.txt"
if diff "$OUT/user-files-before.txt" "$OUT/user-files-after-upgrade.txt" > "$OUT/upgrade-diff.txt"; then
    ok "the upgrade kept every settings, recents, recovery and document file unchanged"
else
    fail "user files changed in the upgrade:"; cat "$OUT/upgrade-diff.txt"
fi
find "$DATA" -maxdepth 2 -type d -name 'recover*' | sort | diff "$OUT/recover-before.txt" - >/dev/null \
    && ok "recovery folders kept" || fail "recovery folders changed"
grep -c "^# BEGIN .*default applications" "$MIMEAPPS" | grep -qx 1 && ok "default applications still set once after the upgrade" \
                                                                    || fail "$MIMEAPPS after upgrade"
gio open "$DOCS/Sample.docx" >>"$OUT/gio-open.log" 2>&1
expect_document "$DOCS/Sample.docx" "double-click after upgrade"
gio launch "/usr/share/applications/$PREFIX-sheet.desktop" >>"$OUT/launch.log" 2>&1 &
wait_window "^EuroOffice Sheet\$" 150 >/dev/null && ok "Sheet starts from its menu entry after the upgrade" || fail "Sheet did not start after the upgrade"
shot 4-after-upgrade
close_apps
snapshot | grep -v "recents.xml\|/recover" > "$OUT/user-files-before-remove.txt"

# -- 5. remove and purge leave user data alone
echo "== remove"
sudo apt-get remove -y -qq "$PKG" > "$OUT/remove.log" 2>&1 || { fail "remove failed"; tail -20 "$OUT/remove.log"; }
for app in $APPS; do
    [ -e "/usr/share/applications/$PREFIX-$app.desktop" ] && fail "$app menu entry left after remove" || ok "$app menu entry removed"
    [ -e "/usr/bin/$PREFIX-$app" ] && fail "/usr/bin/$PREFIX-$app left after remove" || ok "$app command removed"
done
if [ -f "$MIMEAPPS" ] && grep -q "$PREFIX" "$MIMEAPPS"; then fail "$MIMEAPPS still names the applications"; else ok "default applications removed from $MIMEAPPS"; fi
snapshot | grep -v "recents.xml\|/recover" | diff "$OUT/user-files-before-remove.txt" - > "$OUT/remove-diff.txt" \
    && ok "remove kept settings and documents" || { fail "remove changed user files:"; cat "$OUT/remove-diff.txt"; }
sudo apt-get purge -y -qq "$PKG" > "$OUT/purge.log" 2>&1 || { fail "purge failed"; tail -20 "$OUT/purge.log"; }
snapshot | grep -v "recents.xml\|/recover" | diff "$OUT/user-files-before-remove.txt" - > "$OUT/purge-diff.txt" \
    && ok "purge kept settings and documents" || { fail "purge changed user files:"; cat "$OUT/purge-diff.txt"; }
[ -f "$DATA/sos-integration-marker" ] && [ -f "$CONF/sos-integration-marker" ] && ok "user data folders still there after purge" \
                                                                              || fail "user data folders gone after purge"
dpkg -s "$PKG" >/dev/null 2>&1 && fail "$PKG still installed" || ok "$PKG uninstalled"

echo "failures: $FAILS"
exit $((FAILS > 0))
