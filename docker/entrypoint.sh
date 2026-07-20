#!/bin/sh
set -eu

APP_USER="dsa"
APP_GROUP="dsa"
APP_UID="1000"
APP_GID="1000"
WRITABLE_DIRS="/app/data /app/logs /app/reports /home/dsa/.longbridge"
DATABASE_FILE="${DATABASE_PATH:-/app/data/stock_analysis.db}"
EFINANCE_CACHE_FILE="search-cache.json"

warn() {
    printf '%s\n' "$*" >&2
}

repair_efinance_cache_dir() {
    EF_DATA_DIR="$(python -c 'import efinance, pathlib; print(pathlib.Path(efinance.__file__).parent / "data")' 2>/dev/null || true)"
    if [ -z "$EF_DATA_DIR" ]; then
        warn "WARN: unable to resolve efinance data directory; search cache writes may fail and fallback sources will be used."
        return 0
    fi

    if ! mkdir -p "$EF_DATA_DIR"; then
        warn "WARN: unable to create efinance data directory at $EF_DATA_DIR; search cache writes may fail."
        return 0
    fi

    if ! chown -R "$APP_UID:$APP_GID" "$EF_DATA_DIR"; then
        warn "WARN: unable to set ownership for efinance data directory $EF_DATA_DIR; A-share efinance lookups may fallback."
        return 0
    fi

    if ! chmod -R u+rwX "$EF_DATA_DIR"; then
        warn "WARN: unable to adjust permissions for efinance data directory $EF_DATA_DIR."
    fi

    EF_CACHE_FILE="$EF_DATA_DIR/$EFINANCE_CACHE_FILE"
    if [ -e "$EF_CACHE_FILE" ] && ! gosu "$APP_USER:$APP_GROUP" test -w "$EF_CACHE_FILE"; then
        if chown "$APP_UID:$APP_GID" "$EF_CACHE_FILE"; then
            chmod u+rw "$EF_CACHE_FILE" || warn "WARN: unable to adjust permissions for $EF_CACHE_FILE."
        else
            warn "WARN: existing $EF_CACHE_FILE is not writable by $APP_USER and ownership repair failed."
        fi
    fi
}

can_write_dir_as_app_user() {
    gosu "$APP_USER:$APP_GROUP" sh -c '
        tmp="$1/.dsa-write-check.$$"
        : > "$tmp" && rm -f "$tmp"
    ' sh "$1"
}

can_write_file_as_app_user() {
    gosu "$APP_USER:$APP_GROUP" test -w "$1"
}

has_unwritable_mount_path() {
    dir="$1"

    if ! can_write_dir_as_app_user "$dir"; then
        return 0
    fi

    if [ "$dir" = "/app/data" ]; then
        for file in "$DATABASE_FILE" "$DATABASE_FILE-wal" "$DATABASE_FILE-shm"; do
            if [ -e "$file" ] && ! can_write_file_as_app_user "$file"; then
                return 0
            fi
        done
    fi

    return 1
}

directory_needs_repair() {
    dir="$1"

    if has_unwritable_mount_path "$dir"; then
        return 0
    fi

    mismatched_path="$(
        find "$dir" \
            \( ! -user "$APP_UID" -o ! -group "$APP_GID" \) \
            -print -quit 2>/dev/null || true
    )"
    if [ -n "$mismatched_path" ]; then
        return 0
    fi

    return 1
}

if [ "$(id -u)" = "0" ]; then
    repair_efinance_cache_dir

    for dir in $WRITABLE_DIRS; do
        if ! mkdir -p "$dir"; then
            warn "WARN: unable to create $dir; application writes may fail for this path."
            continue
        fi

        if ! directory_needs_repair "$dir"; then
            continue
        fi

        if chown -R "$APP_UID:$APP_GID" "$dir"; then
            if ! chmod -R u+rwX "$dir"; then
                warn "WARN: unable to adjust owner permissions for $dir after ownership repair; check read-only, rootless, or NFS mount permissions if writes fail."
            fi
        else
            warn "WARN: unable to set ownership for $dir; skipping owner-only chmod because it would not grant writes to $APP_USER without ownership."
        fi

        if has_unwritable_mount_path "$dir"; then
            warn "WARN: $dir is still not writable by $APP_USER after permission repair; check host mount ownership or read-only, rootless, and NFS mount settings."
        fi
    done

    HOME="/home/dsa"
    export HOME
    exec gosu "$APP_USER:$APP_GROUP" "$@"
fi

warn "WARN: container entrypoint is not running as root; skipping efinance cache ownership repair."
exec "$@"
