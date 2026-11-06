#!/bin/bash
# Secure Office Suite: security audit of the Ubuntu package itself.
#
#   audit_package_ubuntu.sh <package.deb> <out-dir>
#
# Looks inside the .deb (no install needed) and fails when it finds:
#   1. a file or folder not owned by root:root;
#   2. a setuid or setgid file;
#   3. a file or folder that every user may write to;
#   4. a maintainer script that does not stop at the first error (set -e),
#      or that downloads anything or runs a program from /tmp or a user's home;
#   5. a dependency on a network download tool (curl, wget);
#   6. a URL handler (x-scheme-handler) in a .desktop file, or a .desktop
#      file that hands the application URLs (%u, %U) instead of files;
#   7. a program or library that looks for libraries in the current folder
#      or in a relative folder (RPATH/RUNPATH not starting with $ORIGIN or /).
# Programs or libraries with an executable stack or not built as PIE are
# listed as NOTE: they come from upstream builds and are not new.
set -u

DEB=$1
OUT=$2
mkdir -p "$OUT"
FAILS=0
pass() { echo "PASS: $*"; }
fail() { echo "FAIL: $*"; FAILS=$((FAILS + 1)); }
note() { echo "NOTE: $*"; }

work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT

dpkg-deb --info "$DEB" > "$OUT/info.txt"
dpkg-deb --contents "$DEB" > "$OUT/contents.txt"
dpkg-deb --control "$DEB" "$work/control"
dpkg-deb --extract "$DEB" "$work/root"

# 1. ownership: "drwxr-xr-x root/root ..."
bad=$(awk '$2 != "root/root"' "$OUT/contents.txt")
if [ -z "$bad" ]; then pass "every file and folder is owned by root"
else fail "not owned by root:"; echo "$bad" | head -20; fi

# 2. setuid / setgid (s or S in the user or group execute position)
bad=$(awk 'substr($1,4,1) ~ /[sS]/ || substr($1,7,1) ~ /[sS]/' "$OUT/contents.txt")
if [ -z "$bad" ]; then pass "no setuid or setgid file"
else fail "setuid/setgid:"; echo "$bad" | head -20; fi

# 3. world-writable, symlinks aside (lrwxrwxrwx is how every link looks)
bad=$(awk 'substr($1,1,1) != "l" && substr($1,9,1) == "w"' "$OUT/contents.txt")
if [ -z "$bad" ]; then pass "nothing is writable by every user"
else fail "writable by every user:"; echo "$bad" | head -20; fi

# 4. maintainer scripts
for s in preinst postinst prerm postrm; do
  f=$work/control/$s
  [ -f "$f" ] || continue
  if grep -qE '^[[:space:]]*set -e' "$f"; then pass "$s stops at the first error"
  else fail "$s has no 'set -e'"; fi
  if grep -nE '\b(curl|wget|nc|apt-get|apt|pip|npm)\b[^"]*\b(http|ftp|install)' "$f"; then
    fail "$s downloads or installs something"
  else pass "$s downloads nothing"; fi
  if grep -nE '(^|[^a-zA-Z])(/tmp/|/var/tmp/|\$HOME|~/)' "$f" | grep -vE '^[0-9]+:[[:space:]]*#'; then
    fail "$s uses /tmp or a home folder"
  else pass "$s stays out of /tmp and home folders"; fi
done

# 5. no network download tools pulled in
depends=$(sed -n 's/^ *Depends: //p; s/^ *Pre-Depends: //p; s/^ *Recommends: //p' "$OUT/info.txt" | tr ',|' '\n\n' | sed 's/^ *//; s/ .*//')
if echo "$depends" | grep -qxE 'curl|wget'; then fail "the package depends on curl or wget"
else pass "no dependency on curl or wget"; fi

# 6. .desktop files: files only, no URL handlers
desk=$(find "$work/root/usr/share/applications" -name '*.desktop' 2>/dev/null)
if [ -z "$desk" ]; then fail "no .desktop files found"; fi
for d in $desk; do
  n=$(basename "$d")
  if grep -q 'x-scheme-handler' "$d"; then fail "$n registers a URL handler"; else pass "$n registers no URL handler"; fi
  if grep -E '^Exec=' "$d" | grep -qE '%[uU]'; then fail "$n accepts URLs (%u/%U)"; else pass "$n accepts files only"; fi
done

# 7. ELF files: library search paths, executable stack, PIE
: > "$OUT/elf.txt"
rpath_bad=0; execstack=0; nopie=0
while IFS= read -r -d '' f; do
  head -c 4 "$f" 2>/dev/null | grep -q $'\x7fELF' || continue
  rel=${f#"$work/root"}
  dyn=$(readelf -d "$f" 2>/dev/null)
  for p in $(echo "$dyn" | sed -n 's/.*(R\(UN\)\?PATH).*\[\(.*\)\]/\2/p' | tr ':' ' '); do
    case "$p" in
      '$ORIGIN'*|'${ORIGIN}'*|/*) ;;
      *) echo "rpath $rel: $p" >> "$OUT/elf.txt"; rpath_bad=$((rpath_bad + 1)) ;;
    esac
  done
  # an empty element ("::" or a leading/trailing ":") means the current folder
  if echo "$dyn" | grep -E '\((RUN)?PATH\)' | grep -qE '\[:|::|:\]'; then
    echo "rpath $rel: empty element (current folder)" >> "$OUT/elf.txt"; rpath_bad=$((rpath_bad + 1))
  fi
  if readelf -lW "$f" 2>/dev/null | grep -E 'GNU_STACK' | grep -q 'RWE'; then
    echo "execstack $rel" >> "$OUT/elf.txt"; execstack=$((execstack + 1))
  fi
  if readelf -hW "$f" 2>/dev/null | grep -q 'Type:.*EXEC'; then
    echo "nopie $rel" >> "$OUT/elf.txt"; nopie=$((nopie + 1))
  fi
done < <(find "$work/root" -type f \( -perm -u+x -o -name '*.so*' \) -print0)
if [ "$rpath_bad" = 0 ]; then pass "no program or library looks for libraries in the current or a relative folder"
else fail "$rpath_bad relative library search paths"; grep '^rpath' "$OUT/elf.txt" | head -20; fi
[ "$execstack" = 0 ] || { note "$execstack files with an executable stack"; grep '^execstack' "$OUT/elf.txt" | head -20; }
[ "$nopie" = 0 ] || { note "$nopie programs not built as PIE"; grep '^nopie' "$OUT/elf.txt" | head -20; }

echo
echo "Ubuntu package audit: $FAILS failure(s)"
[ "$FAILS" = 0 ]
