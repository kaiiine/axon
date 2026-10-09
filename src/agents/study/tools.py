"""Study tools — save generated HTML revision sheets and exercises to disk."""
from __future__ import annotations

import re
import subprocess
from datetime import datetime
from pathlib import Path

from langchain_core.tools import tool


def _output_dir() -> Path:
    d = Path.home() / "Documents" / "axon_fiches"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _extract_html(raw: str) -> str:
    """Strip markdown fences if the LLM wrapped the HTML."""
    m = re.search(r"```html\s*(.*?)```", raw, re.DOTALL)
    return m.group(1).strip() if m else raw.strip()


def _open_browser(path: Path) -> None:
    try:
        subprocess.Popen(["xdg-open", str(path)])
    except Exception:
        pass


def _generer_via_skill(file_type: str, content_text: str) -> str:
    """Rend une fiche/exo par le SEUL chemin qui produit une bonne page.

    `skills/fiche.md` (315 lignes) impose une étape d'analyse obligatoire —
    extraire chapitres, définitions, distinctions, pièges d'examen, checklist
    anti-oubli — avant même d'écrire le HTML. Un modèle qui écrit le HTML lui-
    même en pleine conversation n'a jamais vu ces règles : il improvise sur la
    foi des ~26 lignes de design (couleurs, grille) recopiées dans le prompt
    système, sans aucune discipline de CONTENU. D'où des fiches vagues,
    « pas assez précises ».

    Un seul chemin, une seule qualité — que la matière vienne d'un PDF ou
    d'un résumé écrit par le modèle en conversation.
    """
    from langchain_core.messages import HumanMessage

    from src.infra.settings import settings
    from src.llm.models import make_orchestrator_llm_with_key
    from src.llm.prompts import _LANG_INSTRUCTIONS
    from src.llm.rotation import clients, marquer_echec, vaut_la_peine_de_reessayer
    from src.ui.templates import charger

    lang_instruction = _LANG_INSTRUCTIONS.get("fr", "")
    if file_type == "exo":
        prompt = charger("exo", content=content_text, lang=lang_instruction,
                         type_exo="Mélange de QCM (60%) et questions ouvertes (40%).")
    else:
        prompt = charger("fiche", content=content_text, lang=lang_instruction)

    # Une clé épuisée ne doit pas coûter la commande : on parcourt les
    # clés du backend, puis celles des fournisseurs de repli.
    html, derniere = "", None
    for fournisseur, cle, llm in clients(settings.llm_backend, make_orchestrator_llm_with_key):
        try:
            reponse = llm.invoke([HumanMessage(content=prompt)])
            html = reponse.content if isinstance(reponse.content, str) else str(reponse.content)
            break
        except Exception as exc:   # noqa: BLE001 — clé suivante
            derniere = exc
            marquer_echec(fournisseur, cle, exc)
            if not vaut_la_peine_de_reessayer(exc):
                break
    if not html:
        raise RuntimeError(derniere or "aucun fournisseur n'a répondu")
    return html


@tool("save_study_file")
def save_study_file(
    content: str = "",
    file_type: str = "fiche",
    filename: str = "",
    pdf_path: str = "",
    html: str = "",
) -> dict:
    """
    Generates a well-designed HTML study file (revision sheet or interactive
    exercises) and saves it to disk, then opens it in the browser.

    Two ways to provide the material — BOTH go through the same skill-governed
    pipeline (mandatory content analysis, then design), so quality never
    depends on which one you pick:
    - content: your OWN summary of everything to cover — definitions, models,
      distinctions, examples, likely exam points. Write it as thorough
      structured notes, NOT as HTML — the template designs the page from it.
      Use this from a conversation, once the material has been discussed.
    - pdf_path: absolute path to a PDF too large to inject in context. The
      tool extracts and processes it internally.

    `html` still exists as a raw escape hatch — pass a complete HTML document
    only if you deliberately want to bypass the fiche/exo template. Prefer
    `content` : it is what makes the page follow the actual design and
    pedagogical rules instead of an improvised one.

    Args:
        content:   your structured recap of the material (preferred)
        file_type: "fiche" for revision sheets, "exo" for interactive exercises
        filename:  optional base name without extension (e.g. "algo_tri")
        pdf_path:  absolute path to a PDF file (when too large to inject in context)
        html:      complete HTML document — bypasses the template, use only on purpose
    Returns:
        {"status": "ok", "path": str}
        {"status": "error", "error": str}
    """
    # ── Mode PDF : extraire, puis rendre via le skill ──────────────────────────
    if pdf_path and not html and not content:
        p = Path(pdf_path)
        if not p.exists():
            return {"status": "error", "error": f"Fichier introuvable : {pdf_path}"}
        try:
            from src.ui.attachments import _extract_pdf
            content = _extract_pdf(p)
        except Exception as e:
            return {"status": "error", "error": f"Erreur lecture PDF : {e}"}

    # ── Mode contenu : le chemin conversationnel, MÊME pipeline que le PDF ─────
    if content and not html:
        try:
            html = _generer_via_skill(file_type, content)
        except Exception as e:
            return {"status": "error", "error": f"Erreur génération : {e}"}

    # ── Enregistrement ──────────────────────────────────────────────────────
    if not html or len(html) < 200:
        return {"status": "error", "error": "Contenu vide ou trop court."}

    final_html = _extract_html(html)
    ts = datetime.now().strftime("%Y%m%d_%H%M")
    base = filename.strip().replace(" ", "_") or (Path(pdf_path).stem if pdf_path else file_type)
    out = _output_dir() / f"{base}_{ts}.html"

    try:
        out.write_text(final_html, encoding="utf-8")
    except Exception as e:
        return {"status": "error", "error": str(e)}

    _open_browser(out)
    return {
        "status": "ok",
        "path": str(out),
        "message": f"Ouvert dans le navigateur : {out.name}",
    }
