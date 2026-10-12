#!/bin/sh
set -eu
DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
RUNTIME="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
PID_FILE="$RUNTIME/axon/overlay.pid"
alive() {
    [ -r "$PID_FILE" ] || return 1
    PID=$(cat "$PID_FILE")
    case "$PID" in ''|*[!0-9]*) return 1;; esac
    kill -0 "$PID" 2>/dev/null || return 1
    # Vérifie l’identité du processus avant de lui envoyer un signal.
    tr '\000' '\n' < "/proc/$PID/cmdline" | grep -Fx -- "$DIR/overlay.py" >/dev/null
}
if ! alive; then
    sh "$DIR/lancer.sh" >>"$RUNTIME/axon-overlay.log" 2>&1 &
    tries=0
    until alive; do
        tries=$((tries + 1))
        if [ "$tries" -ge 100 ]; then
            echo "Overlay indisponible. Voir $RUNTIME/axon-overlay.log" >&2
            exit 1
        fi
        sleep 0.05
    done
fi
kill -USR1 "$PID"
