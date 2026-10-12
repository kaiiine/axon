# src/utils/write_file.py

from __future__ import annotations
import uuid
from typing import TypedDict, List, Dict
import json
from datetime import datetime, timezone
from src.infra import chemins as _chemins
from src.orchestrator.commun.messages import texte_du_contenu
from langchain_core.utils.function_calling import convert_to_openai_tool


FILE = _chemins.traces_routage_outils()

# ── Typing ───────────────────────────────────────────────────────────

class TraceRecord(TypedDict):
    id: str
    user_message_id: str
    ts: str
    backend: str
    model: str
    tools_offered: List[Dict]
    tool_catalogue_size: int
    messages: List[Dict]
    tool_calls: List[Dict]
    execution: Dict | None
    label: str | None
    signal: str | None
    correction: List[Dict] | None


# ── Tools ───────────────────────────────────────────────────────────

def write_logs(ai_message: Dict, human_message: Dict, selected_tools: List[Dict], messages: Dict[List]) -> None:
    try:
        FILE.parent.mkdir(parents=True, exist_ok=True)
        if not ai_message.tool_calls:
            return 

        logs: TraceRecord = {
            "id":str(uuid.uuid4()),
            "user_message_id": human_message.id,
            "ts": ai_message.response_metadata.get("created_at", datetime.now(timezone.utc).isoformat()),
            "backend": ai_message.response_metadata.get("model_provider", "Backend no found !"),
            "model": ai_message.response_metadata.get("model_name", "Model no found !"),
            "tools_offered": [convert_to_openai_tool(t) for t in selected_tools],
            "tool_catalogue_size": len(selected_tools),
            "messages": [{"role": m.type, "content": texte_du_contenu(m.content)} for m in messages],
            "tool_calls": ai_message.tool_calls,
            "execution": None,
            "label": None,
            "signal": None,
            "correction": None
        }

        
        with open(FILE, 'a') as f:
            f.write(json.dumps(logs, ensure_ascii=False, default=str) + "\n")

    except Exception as e:
        print(e)

