#!/bin/sh
# Démon des rappels (src/cron_daemon.py) au démarrage de la session macOS.
#   sh ops/launchd/installer-rappels.sh            installe et démarre
#   sh ops/launchd/installer-rappels.sh --retirer  arrête et désinstalle
set -eu
LABEL=fr.axon.rappels
RACINE="$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
DOMAINE="gui/$(id -u)"
VENV="$RACINE/.venv"
[ -d "$VENV" ] || VENV="$RACINE/venv"

launchctl bootout "$DOMAINE/$LABEL" 2>/dev/null || true
if [ "${1:-}" = "--retirer" ]; then
    rm -f "$PLIST"
    echo "Démon des rappels retiré."
    exit 0
fi

mkdir -p "$HOME/Library/LaunchAgents" "$HOME/Library/Logs"
cat > "$PLIST" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>WorkingDirectory</key><string>$RACINE</string>
  <key>ProgramArguments</key>
  <array>
    <string>$VENV/bin/python</string>
    <string>-m</string>
    <string>src.cron_daemon</string>
  </array>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><dict><key>SuccessfulExit</key><false/></dict>
  <key>StandardOutPath</key><string>$HOME/Library/Logs/axon-rappels.log</string>
  <key>StandardErrorPath</key><string>$HOME/Library/Logs/axon-rappels.log</string>
</dict>
</plist>
PLIST
launchctl bootstrap "$DOMAINE" "$PLIST"
echo "Démon des rappels installé ($PLIST)."
