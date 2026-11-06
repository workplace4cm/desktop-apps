#!/bin/bash
# Secure Office Suite: repair library search paths (RPATH/RUNPATH) that the
# build mangled.
#
#   fix-rpath.sh <folder>
#
# '$ORIGIN' (the program's own folder) gets eaten by one level of make or
# qmake variable expansion too many, leaving "$", "$/converter" or "RIGIN".
# Those are RELATIVE folders, looked up from wherever the user happens to be:
# a folder named "$" or "RIGIN" there, holding a library of the right name,
# would be loaded into the editors. This puts $ORIGIN back and drops any
# other relative entry, so libraries come only from the application's own
# folders and the system.
set -euo pipefail

root=$1
command -v patchelf >/dev/null || { echo "fix-rpath.sh: patchelf is required" >&2; exit 1; }

fixed=0
while IFS= read -r -d '' f; do
  head -c 4 "$f" 2>/dev/null | grep $'\x7fELF' >/dev/null || continue
  old=$(patchelf --print-rpath "$f" 2>/dev/null) || continue
  [ -n "$old" ] || continue
  new=""
  IFS=':' read -r -a parts <<< "$old"
  for p in "${parts[@]}"; do
    case "$p" in
      '$ORIGIN'*|/*) q=$p ;;
      '$'|'$/'*)     q='$ORIGIN'${p#\$} ;;
      RIGIN|RIGIN/*) q='$ORIGIN'${p#RIGIN} ;;
      *)             q="" ;;   # empty or other relative entry: dropped
    esac
    [ -n "$q" ] || continue
    case ":$new:" in *":$q:"*) ;; *) new=${new:+$new:}$q ;; esac
  done
  if [ "$new" != "$old" ]; then
    # keep the entry's kind: DT_RPATH also covers the libraries' own
    # dependencies, DT_RUNPATH only the file's direct ones
    force=--force-rpath
    readelf -d "$f" 2>/dev/null | grep '(RUNPATH)' >/dev/null && force=""
    if [ -n "$new" ]; then patchelf $force --set-rpath "$new" "$f"; else patchelf --remove-rpath "$f"; fi
    echo "rpath ${f#"$root"}: $old -> ${new:-(none)}"
    fixed=$((fixed + 1))
  fi
done < <(find "$root" -type f \( -perm -u+x -o -name '*.so*' \) -print0)
echo "fix-rpath.sh: $fixed files repaired"
