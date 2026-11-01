#!/bin/bash
# Secure Office Suite: checks that EuroOffice Writer, Sheet, Presentation and
# PDF run as four independent applications from the installed package.
#
#   verify_apps.sh <prefix> <out-dir>
#     prefix   installed command prefix, e.g. secure-office-suite-desktopeditors
#     out-dir  where screenshots and logs go
#
# Needs an X server on $DISPLAY with a window manager, xdotool and xprop.
# Checks:
#   1. a document passed at launch opens directly in its application,
#      without a start page or launcher first;
#   2. each application starts on its own start page, in its own process,
#      with its own window title, WM_CLASS and Wayland/desktop identity;
#   3. launching a running application again reaches the same process;
#   4. a document given to the wrong application (or to the suite command)
#      opens in the right one, and the wrong one doesn't show it;
#   5. each application keeps its own browser profile and recovery folder.

set -u
PREFIX=${1:?prefix}
OUT=${2:?out dir}
mkdir -p "$OUT"
DOCS=$(mktemp -d)
FAILS=0
APP_DIR=/opt/$(echo "$PREFIX" | sed 's/-desktopeditors$//')/desktopeditors
DATA=$HOME/.local/share/$(echo "$PREFIX" | sed 's/-desktopeditors$//')/desktopeditors

ok()   { echo "PASS: $*"; }
fail() { echo "FAIL: $*"; FAILS=$((FAILS + 1)); }
shot() { import -window root "$OUT/$1.png" 2>/dev/null || true; }

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

wm_class() {
    local w
    w=$(xdotool search --onlyvisible --name "$1" 2>/dev/null | head -1)
    [ -n "$w" ] && xprop -id "$w" WM_CLASS 2>/dev/null
}

app_pids() {   # main processes of one application
    pgrep -u "$(id -u)" -f -- "$APP_DIR/DesktopEditors --app=$1" | sort -u
}

titles() {
    for w in $(xdotool search --onlyvisible --name '.' 2>/dev/null); do xdotool getwindowname "$w"; done | sort -u
}

# sample documents: the blank files the package ships for "New" menus
EMPTY=$APP_DIR/converter/empty/default
[ -d "$EMPTY" ] || EMPTY=$(dirname "$(find "$APP_DIR/converter/empty" -name new.docx | head -1)")
cp "$EMPTY/new.docx" "$DOCS/Report.docx"
cp "$EMPTY/new.xlsx" "$DOCS/Budget.xlsx"
cp "$EMPTY/new.pptx" "$DOCS/Deck.pptx"
cp "$EMPTY/new.pdf"  "$DOCS/Form.pdf"
cp "$EMPTY/new.xlsx" "$DOCS/Routed.xlsx"
cp "$EMPTY/new.docx" "$DOCS/Second.docx"
ls -l "$DOCS"

# -- 1. a document opens directly in its application
( "$PREFIX-presentation" "$DOCS/Deck.pptx"; echo "exited with status $?" ) >"$OUT/presentation.log" 2>&1 &
if pid=$(wait_window '^\*?Deck\.pptx.* - EuroOffice Presentation$'); then
    ok "Deck.pptx opened directly in EuroOffice Presentation (pid $pid)"
else
    fail "Deck.pptx did not open in EuroOffice Presentation"
fi
shot 1-presentation-document

# -- 2. each application on its own start page, own process and identity
declare -A PID
for app in writer sheet pdf; do
    case $app in writer) name="EuroOffice Writer";; sheet) name="EuroOffice Sheet";; pdf) name="EuroOffice PDF";; esac
    ( "$PREFIX-$app"; echo "exited with status $?" ) >"$OUT/$app.log" 2>&1 &
    if p=$(wait_window "^$name\$"); then
        PID[$app]=$p
        ok "$name started on its start page (pid $p)"
        cls=$(wm_class "^$name\$")
        case "$cls" in *"\"$name\""*) ok "$name WM_CLASS: $cls";; *) fail "$name WM_CLASS is '$cls'";; esac
    else
        fail "$name did not show its start page"
    fi
    shot "2-$app-start-page"
    pgrep -f -- "--app=presentation" >/dev/null || echo "note: no Presentation process after $app started"
done
PID[presentation]=$(app_pids presentation | head -1)

distinct=$(printf '%s\n' "${PID[@]}" | grep -v '^$' | sort -u | wc -l)
[ "$distinct" = 4 ] && ok "four applications, four processes: ${PID[*]}" || fail "processes: ${PID[*]} ($distinct distinct)"
for app in writer sheet presentation pdf; do
    n=$(app_pids $app | wc -l)
    [ "$n" = 1 ] && ok "one $app process" || fail "$n $app processes"
done

# -- 3. launching Writer again reaches the running Writer
"$PREFIX-writer" "$DOCS/Second.docx" >>"$OUT/writer.log" 2>&1
if p=$(wait_window '^\*?Second\.docx.* - EuroOffice Writer$'); then
    [ "$p" = "${PID[writer]:-}" ] && ok "Second.docx opened in the running Writer (pid $p)" \
                                  || fail "Second.docx opened in pid $p, Writer is ${PID[writer]:-?}"
else
    fail "Second.docx did not open in Writer"
fi
[ "$(app_pids writer | wc -l)" = 1 ] && ok "still one Writer process" || fail "a second Writer process stayed"
shot 3-writer-second-document

# -- 4. a spreadsheet given to Writer opens in Sheet
"$PREFIX-writer" "$DOCS/Routed.xlsx" >>"$OUT/writer.log" 2>&1
if p=$(wait_window '^\*?Routed\.xlsx.* - EuroOffice Sheet$'); then
    [ "$p" = "${PID[sheet]:-}" ] && ok "Routed.xlsx given to Writer opened in Sheet (pid $p)" \
                                 || fail "Routed.xlsx opened in pid $p, Sheet is ${PID[sheet]:-?}"
else
    fail "Routed.xlsx did not open in Sheet"
fi
titles | grep -q "Routed.xlsx.* - EuroOffice Writer" && fail "Writer shows Routed.xlsx too" || ok "Writer did not open Routed.xlsx"
shot 4-routed-to-sheet

# the suite command with a PDF opens EuroOffice PDF
"$PREFIX" "$DOCS/Form.pdf" >"$OUT/suite.log" 2>&1
if p=$(wait_window '^\*?Form\.pdf.* - EuroOffice PDF$'); then
    [ "$p" = "${PID[pdf]:-}" ] && ok "Form.pdf from the suite command opened in PDF (pid $p)" \
                               || fail "Form.pdf opened in pid $p, PDF is ${PID[pdf]:-?}"
else
    fail "Form.pdf did not open in EuroOffice PDF"
fi
pgrep -u "$(id -u)" -f -- "$APP_DIR/DesktopEditors$" >/dev/null && fail "the suite process stayed" || ok "the suite command handed over and quit"

# a new spreadsheet asked of Writer (--new:cell) is made by Sheet
before=$(titles | grep -- " - EuroOffice Sheet$")
"$PREFIX-writer" --new:cell >>"$OUT/writer.log" 2>&1
new=""
for _ in $(seq 90); do
    new=$(titles | grep -- " - EuroOffice Sheet$" | grep -vxF -- "$before")
    [ -n "$new" ] && break
    sleep 1
done
[ -n "$new" ] && ok "--new:cell given to Writer made a spreadsheet in Sheet ($new)" || fail "--new:cell did not reach Sheet"
extra=$(titles | grep -- " - EuroOffice Writer$" | grep -v "Second\.docx")
[ -z "$extra" ] && ok "Writer made no spreadsheet" || fail "Writer shows: $extra"
shot 5-all

# -- 5. separate profiles and recovery folders
for app in writer sheet presentation pdf; do
    d=$(find "$DATA" -maxdepth 2 -type d -name "cache-$app" | head -1)
    [ -n "$d" ] && ok "$app has its own browser profile ($d)" || fail "no cache-$app under $DATA"
    r=$(find "$DATA" -maxdepth 2 -type d -name "recover-$app" | head -1)
    [ -n "$r" ] && ok "$app has its own recovery folder" || fail "no recover-$app under $DATA"
done

# desktop entries and icons of the four applications
for app in writer sheet presentation pdf; do
    f=/usr/share/applications/$PREFIX-$app.desktop
    desktop-file-validate "$f" && ok "$f is valid" || fail "$f does not validate"
    [ -x "/usr/bin/$PREFIX-$app" ] && ok "/usr/bin/$PREFIX-$app" || fail "no /usr/bin/$PREFIX-$app"
    [ -f "/usr/share/icons/hicolor/256x256/apps/$PREFIX-$app.png" ] && ok "$app icon" || fail "no $app icon"
done

titles > "$OUT/titles.txt"
ps -o pid,args -u "$(id -u)" | grep "[D]esktopEditors" > "$OUT/processes.txt"
echo "--- windows"; cat "$OUT/titles.txt"
echo "--- processes"; cat "$OUT/processes.txt"
if [ "$FAILS" -gt 0 ]; then
    for f in "$OUT"/*.log; do echo "--- $f"; tail -n 60 "$f"; done
    echo "--- all windows"
    for w in $(xdotool search --name '.' 2>/dev/null); do echo "$w $(xdotool getwindowname "$w" 2>/dev/null)"; done
    echo "--- data folder"; find "$DATA" -maxdepth 2 2>/dev/null | head -40
fi
echo "failures: $FAILS"
exit $((FAILS > 0))
