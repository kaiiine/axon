#!/bin/sh
# Lance l'overlay avec gtk4-layer-shell préchargé (obligatoire en Python).
#
# /usr/bin/python3 EXPLICITEMENT, pas juste "python3" : si un venv (celui
# d'Axon, par exemple) est activé dans le shell qui lance ce script, "python3"
# résoudrait vers le python du venv — qui n'a pas `gi` (PyGObject vit dans le
# python SYSTÈME, installé par pacman). Vécu : "ModuleNotFoundError: No
# module named 'gi'" alors que python-gobject était bien installé.
DIR="$(cd "$(dirname "$0")" && pwd)"
# Chemin ABSOLU vers overlay.py, pas juste "overlay.py" après un cd : sinon
# son cmdline ne contient jamais "axon-overlay/", et tous les pkill -f
# "axon-overlay/overlay.py" (waybar-toggle.sh, bind SUPER+A, ...) ne
# trouvent jamais le process déjà lancé — le clic/raccourci ne fait rien.
#
# Contournement WebKit conservé depuis l’archive fournie (NVIDIA/bwrap).
# AXON_WEBKIT_SANDBOX=1 permet de réactiver le sandbox sur une machine compatible.
# Le front est local ; cette exception n’est pas adaptée à la navigation distante.
if [ ! -f "$DIR/ui/dist/axon.js" ]; then
    echo "Front compilé absent : exécute npm ci puis npm run build dans $DIR" >&2
    exit 1
fi
if [ "${AXON_WEBKIT_SANDBOX:-0}" = "1" ]; then
    unset WEBKIT_DISABLE_SANDBOX_THIS_IS_DANGEROUS
else
    export WEBKIT_DISABLE_SANDBOX_THIS_IS_DANGEROUS=1
fi
exec env LD_PRELOAD="${AXON_LAYER_SHELL_LIB:-/usr/lib/libgtk4-layer-shell.so}${LD_PRELOAD:+:$LD_PRELOAD}" /usr/bin/python3 "$DIR/overlay.py"
