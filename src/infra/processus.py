"""Savoir si un processus tourne, sur tous les systèmes."""
from __future__ import annotations

import os
import sys
from pathlib import Path


def vivant(pid: int) -> bool:
    """Sous Windows, `os.kill(pid, 0)` TERMINE le processus au lieu de le
    sonder : on interroge son code de sortie à la place."""
    if sys.platform == "win32":
        import ctypes
        noyau = ctypes.windll.kernel32
        poignee = noyau.OpenProcess(0x1000, False, pid)   # PROCESS_QUERY_LIMITED_INFORMATION
        if not poignee:
            return False
        try:
            code = ctypes.c_ulong()
            return bool(noyau.GetExitCodeProcess(poignee, ctypes.byref(code))) and code.value == 259
        finally:
            noyau.CloseHandle(poignee)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        pass  # existe, juste pas à nous — toujours vivant
    return True


def pid_vivant(fichier: Path) -> int | None:
    """Le PID écrit dans `fichier` s'il désigne un processus vivant."""
    try:
        pid = int(fichier.read_text().strip())
    except (ValueError, OSError):
        return None
    return pid if vivant(pid) else None
