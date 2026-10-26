"""Lecture et écriture du `.env` sans le réordonner ni perdre ses commentaires."""
from __future__ import annotations

from pathlib import Path

#: Valeurs d'exemple de `.env.sample`, qui ne comptent pas comme renseignées.
_EXEMPLES = ("Ton Prénom Nom",)


class FichierEnv:
    def __init__(self, chemin: Path) -> None:
        self.chemin = chemin

    def _lignes(self) -> list[str]:
        if not self.chemin.exists():
            return []
        return self.chemin.read_text(encoding="utf-8").splitlines()

    def lire(self, cle: str) -> str:
        prefixe = f"{cle}="
        for ligne in self._lignes():
            if ligne.startswith(prefixe):
                return ligne[len(prefixe):].strip().strip('"').strip("'")
        return ""

    def ecrire(self, cle: str, valeur: str) -> None:
        """Remplace la ligne `cle=…` à sa place, ou l'ajoute à la fin."""
        prefixe = f"{cle}="
        lignes = self._lignes()
        nouvelle = f"{cle}={valeur}"
        for i, ligne in enumerate(lignes):
            if ligne.startswith(prefixe):
                lignes[i] = nouvelle
                break
        else:
            lignes.append(nouvelle)
        self.chemin.write_text("\n".join(lignes) + "\n", encoding="utf-8")

    def renseignee(self, cle: str) -> bool:
        return est_renseignee(self.lire(cle))


def est_renseignee(valeur: str) -> bool:
    """Vrai pour une vraie valeur, faux pour un vide ou un exemple (`tvly-...`)."""
    return bool(valeur) and "..." not in valeur and not valeur.startswith("your_") \
        and valeur not in _EXEMPLES
