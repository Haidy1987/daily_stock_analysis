#!/bin/sh
set -eu

resolve_efinance_data_dir() {
  python - <<'PY'
import pathlib

try:
    import efinance
except Exception:
    raise SystemExit(1)

print(pathlib.Path(efinance.__file__).parent / "data")
PY
}

EF_DATA_DIR="${EFINANCE_DATA_DIR:-$(resolve_efinance_data_dir || true)}"
if [ -z "$EF_DATA_DIR" ]; then
  echo "FAIL: unable to resolve efinance data directory" >&2
  exit 1
fi

mkdir -p "$EF_DATA_DIR"

TMP_FILE="$EF_DATA_DIR/.dsa-permission-smoke.$$"
printf 'ok' > "$TMP_FILE"
printf 'updated' >> "$TMP_FILE"
rm -f "$TMP_FILE"

if [ -e "$EF_DATA_DIR/search-cache.json" ]; then
  test -w "$EF_DATA_DIR/search-cache.json"
fi

echo "OK: efinance data directory is writable at $EF_DATA_DIR"
