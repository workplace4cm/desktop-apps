#!/bin/bash
# Runs inside the stock Ubuntu desktop container (as root, --network none):
#   run_in_container.sh <tools-dir> <new-deb> <out-dir> [<previous-deb>]
# Starts a virtual display and, as the user "tester", runs the release
# checks, then the build's own application and integration checks against
# the offline-installed package. Writes <out-dir>/<step>.log and RESULT.
set -u
TOOLS=$1 NEW=$2 OUT=$3 OLD=${4:-}
PREFIX=secure-office-suite-desktopeditors
mkdir -p "$OUT" && chmod 777 "$OUT"
cp -r "$TOOLS" /opt/sos-tools && chmod -R a+rX /opt/sos-tools
cp "$NEW" /tmp/new.deb; [ -n "$OLD" ] && cp "$OLD" /tmp/old.deb
chmod a+r /tmp/*.deb
Xvfb :99 -screen 0 1600x1000x24 >/dev/null 2>&1 & sleep 3
cat /stock-manifest-name > "$OUT/stock-manifest.txt"; . /etc/os-release; echo "$PRETTY_NAME" >> "$OUT/stock-manifest.txt"
as_tester() {
    sudo -u tester -H env SOS_REQUIRE_NEWER=${SOS_REQUIRE_NEWER:-1} DISPLAY=:99 LIBGL_ALWAYS_SOFTWARE=1 QT_QPA_PLATFORM=xcb NO_AT_BRIDGE=1 \
        dbus-run-session -- bash -c 'openbox >/dev/null 2>&1 & sleep 2; xdg-user-dirs-update; "$@"' _ "$@"
}
status=0
as_tester /opt/sos-tools/verify_release_ubuntu.sh $PREFIX /tmp/new.deb "$OUT/release" $([ -n "$OLD" ] && echo /tmp/old.deb) \
    > "$OUT/release.log" 2>&1 || status=1
if dpkg -s $PREFIX >/dev/null 2>&1; then
    as_tester /opt/sos-tools/verify_apps.sh $PREFIX "$OUT/apps" > "$OUT/apps.log" 2>&1 || status=1
    as_tester /opt/sos-tools/verify_integration.sh $PREFIX /tmp/new.deb "$OUT/integration" > "$OUT/integration.log" 2>&1 || status=1
else
    echo "FAIL: the package is not installed after the release checks" | tee "$OUT/apps.log" > "$OUT/integration.log"; status=1
fi
for l in release apps integration; do
    echo "$l: $(grep -c '^PASS' "$OUT/$l.log") passed, $(grep -c '^FAIL' "$OUT/$l.log") failed"
done | tee "$OUT/RESULT"
chmod -R a+rX "$OUT"
exit $status
