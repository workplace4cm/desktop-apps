#!/bin/bash
# Secure Office Suite: release checks of the Ubuntu package that the build's
# own checks (verify_apps.sh, verify_integration.sh) don't make, on a machine
# with no network at all (the release workflow runs it in a stock Ubuntu
# desktop container started with --network none).
#
#   verify_release_ubuntu.sh <prefix> <new-deb> <out-dir> [<previous-deb>]
#     prefix        installed command prefix, e.g. secure-office-suite-desktopeditors
#     new-deb       the package being released
#     out-dir       where screenshots and logs go
#     previous-deb  an earlier build, installed first so that the new one is
#                   a real upgrade (optional: without it the new package is
#                   installed on the clean machine)
#
# Needs an X server on $DISPLAY with a window manager, xdotool, gio and
# password-less sudo. Checks:
#   1. the machine is clean and offline;
#   2. clean install (or the previous build) with dpkg only, no network;
#   3. each application opens a document of its own, so the user has
#      documents, recent documents, settings and browser profiles;
#   4. upgrade to the new package: version grows (SOS_REQUIRE_NEWER=0 allows
#      two builds of the same version, as before Phase 10), every user file is kept
#      unchanged, the recent documents are still listed after each
#      application has started again;
#   5. uninstall (purge) keeps user data, reinstall offline brings back the
#      menus, default applications and commands, and the applications start
#      with the user's recent documents.
# It prints PASS/FAIL lines and ends with "failures: N".

set -u
PREFIX=${1:?prefix}
NEW=$(readlink -f "${2:?new deb}")
OUT=${3:?out dir}
OLD=${4:-}
[ -n "$OLD" ] && OLD=$(readlink -f "$OLD")
mkdir -p "$OUT"
HERE=$(cd "$(dirname "$0")" && pwd)
FAILS=0
PKG=$(dpkg-deb -f "$NEW" Package)
BASE=$(echo "$PREFIX" | sed 's/-desktopeditors$//')
APP_DIR=/opt/$BASE/desktopeditors
DATA=$HOME/.local/share/$BASE/desktopeditors
CONF=$HOME/.config/$BASE
DOCS=$HOME/Documents/sos-release
RECENTS=$DATA/sos-recents.json
MIMEAPPS=/etc/xdg/mimeapps.list
APPS="writer sheet presentation pdf"

ok()   { echo "PASS: $*"; }
fail() { echo "FAIL: $*"; FAILS=$((FAILS + 1)); }
shot() { import -window root "$OUT/$1.png" 2>/dev/null || true; }

app_name() {
    case $1 in
        writer) echo "SecureOffice Writer";; sheet) echo "SecureOffice Sheet";;
        presentation) echo "SecureOffice Presentation";; pdf) echo "SecureOffice PDF";;
    esac
}
sample_of() {
    case $1 in writer) echo Sample.docx;; sheet) echo Sample.xlsx;; presentation) echo Sample.pptx;; pdf) echo Sample.pdf;; esac
}

wait_window() {   # pid of the first window whose title matches $1, within $2 s
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
app_of_pid() { tr '\0' '\n' < "/proc/$1/cmdline" 2>/dev/null | sed -n 's/^--app=//p' | head -1; }
titles() { for w in $(xdotool search --onlyvisible --name '.' 2>/dev/null); do xdotool getwindowname "$w"; done | sort -u; }

close_apps() {
    pkill -u "$(id -u)" -f -- "$APP_DIR/DesktopEditors" 2>/dev/null
    for _ in $(seq 30); do
        pgrep -u "$(id -u)" -f -- "$APP_DIR/DesktopEditors" >/dev/null || return 0
        sleep 1
    done
    pkill -9 -u "$(id -u)" -f -- "$APP_DIR/DesktopEditors" 2>/dev/null
    sleep 2
}

# open the application's sample document with its own command: $1 = app, $2 = when
open_document() {
    local app=$1 when=$2 f name re pid
    f=$DOCS/$(sample_of "$app"); name=$(app_name "$app")
    ( "/usr/bin/$PREFIX-$app" "$f"; echo "exited with status $?" ) >>"$OUT/$app.log" 2>&1 &
    re="^\*?$(basename "$f" | sed 's/\./\\./g')( .*)? - $name\$"
    if pid=$(wait_window "$re" 150); then
        [ "$(app_of_pid "$pid")" = "$app" ] && ok "$name opened $(basename "$f") ($when, pid $pid)" \
                                           || fail "$(basename "$f") opened in pid $pid ($(app_of_pid "$pid")) ($when)"
    else
        fail "$name did not open $(basename "$f") ($when)"
        titles | sed 's/^/    window: /'
        tail -20 "$OUT/$app.log" | sed 's/^/    log: /'
    fi
}

# a launcher starts its application on its start page: $1 = app, $2 = when
start_app() {
    local app=$1 when=$2 name pid
    name=$(app_name "$app")
    gio launch "/usr/share/applications/$PREFIX-$app.desktop" >>"$OUT/launch.log" 2>&1 &
    if pid=$(wait_window "^$name\$" 150); then
        [ "$(app_of_pid "$pid")" = "$app" ] && ok "the $name menu entry starts $name ($when)" \
                                           || fail "the $name menu entry started $(app_of_pid "$pid") ($when)"
    else
        fail "the $name menu entry did not start $name ($when)"
    fi
}

# is the application's sample document in its recent documents? $1 = app
in_recents() {
    [ -s "$RECENTS" ] || return 1
    python3 - "$RECENTS" "$DOCS/$(sample_of "$1")" "$1" <<'EOF'
import json, os, sys
store, path, app = sys.argv[1], sys.argv[2], sys.argv[3]
d = json.load(open(store))
def entries(x):
    if isinstance(x, dict):
        if 'path' in x:
            yield x
        for v in x.values():
            yield from entries(v)
    elif isinstance(x, list):
        for v in x:
            yield from entries(v)
hit = [e for e in entries(d) if os.path.normpath(str(e.get('path', ''))) == os.path.normpath(path)
       and e.get('app', app) == app and not e.get('removed')]
sys.exit(0 if hit else 1)
EOF
}

# each sample document is in the recent documents of its application
check_recents() {   # $1 = when
    local app f
    if [ ! -s "$RECENTS" ]; then fail "no $RECENTS ($1)"; return; fi
    for app in $APPS; do
        f=$(sample_of "$app")
        if in_recents "$app"; then ok "$f is in the $app recent documents ($1)"; else fail "$f is not in the $app recent documents ($1)"; fi
    done
}

# An application records a document once the editor has loaded it, a little
# after its window title shows the name. Give each one up to 60 s before the
# applications are closed, as a user would.
wait_recents() {
    local app
    for app in $APPS; do
        for _ in $(seq 60); do in_recents "$app" && break; sleep 1; done
    done
}

snapshot() {   # user files that must survive, with checksums (browser caches excluded)
    { find "$DATA" "$CONF" -type f ! -path '*/cache*' ! -name '*.lock' ! -name 'LOCK' ! -name '*.bak' 2>/dev/null
      find "$DOCS" -type f; } | sort | xargs -r -d '\n' sha256sum
}

install_offline() {   # $1 = deb, $2 = log name
    sudo dpkg -i "$1" > "$OUT/$2.log" 2>&1
}

check_installed() {   # menus, commands and default applications: $1 = when
    local app visible
    visible=$(grep -L -x 'NoDisplay=true' /usr/share/applications/"$PREFIX"*.desktop 2>/dev/null | xargs -r -n1 basename | sed 's/\.desktop$//' | sort | tr '\n' ' ')
    [ "$visible" = "$(for a in $APPS; do echo "$PREFIX-$a"; done | sort | tr '\n' ' ')" ] \
        && ok "four application menu entries ($1)" || fail "menu entries: $visible ($1)"
    for app in $APPS; do
        [ -x "/usr/bin/$PREFIX-$app" ] || fail "no /usr/bin/$PREFIX-$app ($1)"
    done
    grep -c "^# BEGIN .*default applications" "$MIMEAPPS" 2>/dev/null | grep -qx 1 \
        && ok "default applications set once ($1)" || fail "$MIMEAPPS ($1)"
    local def
    def=$(gio mime application/vnd.openxmlformats-officedocument.wordprocessingml.document 2>/dev/null | sed -n 's/^Default application for .*: //p')
    [ "$def" = "$PREFIX-writer.desktop" ] && ok "DOCX opens with Writer ($1)" || fail "DOCX default is '$def' ($1)"
}

# ------------------------------------------------------------ 1. clean, offline
echo "== clean machine"
if timeout 5 bash -c 'exec 3<>/dev/tcp/1.1.1.1/443' 2>/dev/null || getent hosts github.com >/dev/null 2>&1; then
    fail "this machine has network access; the release checks must run offline"
else
    ok "no network: offline installation and use"
fi
dpkg -s "$PKG" >/dev/null 2>&1 && fail "$PKG is already installed" || ok "$PKG not installed"
[ -e "$APP_DIR" ] && fail "$APP_DIR exists before installing" || ok "no $APP_DIR"
ls /usr/share/applications/"$PREFIX"*.desktop >/dev/null 2>&1 && fail "menu entries before installing" || ok "no menu entries before installing"
mkdir -p "$DOCS"
cp "$HERE"/samples/Sample.* "$DOCS/"
rm -f "$DOCS/README.md"

# ------------------------------------------------------------ 2. install
FIRST=${OLD:-$NEW}
echo "== install $(basename "$FIRST")"
if install_offline "$FIRST" install; then ok "dpkg installed $(basename "$FIRST") with no network"
else fail "dpkg could not install $(basename "$FIRST") offline"; cat "$OUT/install.log"; echo "failures: $FAILS"; exit 1; fi
missing=$(cd "$APP_DIR" && LD_LIBRARY_PATH=$APP_DIR:$APP_DIR/converter ldd DesktopEditors converter/x2t 2>/dev/null | grep "not found" | sort -u)
[ -z "$missing" ] && ok "every library the applications load is present" || fail "missing libraries: $missing"
check_installed "after install"

# ------------------------------------------------------- 3. use the applications
echo "== use"
for app in $APPS; do
    open_document "$app" "$( [ -n "$OLD" ] && echo "previous build" || echo "first use")"
done
shot 3-documents
wait_recents
close_apps
check_recents "before the upgrade"
mkdir -p "$DATA" "$CONF"
echo "user data $(date)" > "$DATA/sos-release-marker"
echo "settings $(date)" > "$CONF/sos-release-marker"
snapshot > "$OUT/user-files-before.txt"
echo "user files: $(wc -l < "$OUT/user-files-before.txt")"

# ------------------------------------------------------------ 4. upgrade
if [ -n "$OLD" ]; then
    echo "== upgrade"
    v0=$(dpkg-query -W -f '${Version}' "$PKG"); v1=$(dpkg-deb -f "$NEW" Version)
    if dpkg --compare-versions "$v1" gt "$v0"; then ok "the new package's version $v1 is newer than the installed $v0"
    elif [ "$v1" = "$v0" ] && [ "${SOS_REQUIRE_NEWER:-1}" = 0 ]; then
        echo "NOTE: both builds are version $v1 (built before versions grew per build); dpkg reinstalls it"
    else fail "the new package's version $v1 is not newer than the installed $v0: package managers would not offer it as an upgrade"; fi
    if install_offline "$NEW" upgrade; then ok "upgraded offline with dpkg"; else fail "upgrade failed"; tail -20 "$OUT/upgrade.log"; fi
    [ "$(dpkg-query -W -f '${Version}' "$PKG")" = "$v1" ] && ok "installed version is now $v1" || fail "installed version $(dpkg-query -W -f '${Version}' "$PKG")"
    snapshot > "$OUT/user-files-after-upgrade.txt"
    diff "$OUT/user-files-before.txt" "$OUT/user-files-after-upgrade.txt" > "$OUT/upgrade-diff.txt" \
        && ok "the upgrade kept every user file unchanged" || { fail "user files changed in the upgrade:"; cat "$OUT/upgrade-diff.txt"; }
    check_installed "after upgrade"
    for app in $APPS; do start_app "$app" "after upgrade"; done
    shot 4-after-upgrade
    sleep 3
    close_apps
    check_recents "after the upgrade and a restart"
    for app in $APPS; do open_document "$app" "after upgrade"; done
    close_apps
fi

# ------------------------------------------------ 5. uninstall and reinstall
echo "== uninstall"
snapshot | grep -v "sos-recents\|recents.xml\|/recover" > "$OUT/user-files-before-uninstall.txt"
sudo dpkg --purge "$PKG" > "$OUT/purge.log" 2>&1 && ok "purged $PKG" || { fail "purge failed"; tail -20 "$OUT/purge.log"; }
[ -e "$APP_DIR/DesktopEditors" ] && fail "program files left" || ok "program files removed"
ls /usr/share/applications/"$PREFIX"*.desktop >/dev/null 2>&1 && fail "menu entries left" || ok "menu entries removed"
grep -q "$PREFIX" "$MIMEAPPS" 2>/dev/null && fail "default applications left in $MIMEAPPS" || ok "default applications removed"
snapshot | grep -v "sos-recents\|recents.xml\|/recover" | diff "$OUT/user-files-before-uninstall.txt" - > "$OUT/uninstall-diff.txt" \
    && ok "uninstall kept settings, profiles and documents" || { fail "uninstall changed user files:"; cat "$OUT/uninstall-diff.txt"; }
[ -s "$RECENTS" ] && ok "recent documents kept after uninstall" || fail "recent documents gone after uninstall"

echo "== reinstall"
if install_offline "$NEW" reinstall; then ok "reinstalled offline with dpkg"; else fail "reinstall failed"; tail -20 "$OUT/reinstall.log"; fi
check_installed "after reinstall"
snapshot | grep -v "sos-recents\|recents.xml\|/recover" | diff "$OUT/user-files-before-uninstall.txt" - > "$OUT/reinstall-diff.txt" \
    && ok "reinstall kept settings, profiles and documents" || { fail "reinstall changed user files:"; cat "$OUT/reinstall-diff.txt"; }
for app in $APPS; do start_app "$app" "after reinstall"; done
shot 5-after-reinstall
sleep 3
close_apps
check_recents "after reinstalling"
gio open "$DOCS/Sample.odt" >>"$OUT/gio-open.log" 2>&1
wait_window '^\*?Sample\.odt( .*)? - SecureOffice Writer$' 150 >/dev/null && ok "double-click on Sample.odt opens Writer after reinstall" \
                                                                    || fail "Sample.odt did not open in Writer after reinstall"
close_apps

echo "failures: $FAILS"
exit $((FAILS > 0))
