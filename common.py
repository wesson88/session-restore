"""llh common helpers: IR build/merge/load."""
import json
import time
from pathlib import Path

import config


def approx_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime())


def ms_to_iso(ms) -> str:
    try:
        return time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(int(ms) / 1000))
    except Exception:
        return ""


def text_from_content(content):
    """content: str | list[dict] -> (text, tool_notes)"""
    if content is None:
        return "", []
    if isinstance(content, str):
        return content.strip(), []
    parts, notes = [], []
    for b in content:
        if not isinstance(b, dict):
            continue
        t = b.get("type")
        if t == "text":
            parts.append(b.get("text", ""))
        elif t == "tool_use":
            name = b.get("name", "tool")
            try:
                inp = json.dumps(b.get("input", {}), ensure_ascii=False)[:80]
            except Exception:
                inp = ""
            notes.append(f"工具调用 {name}({inp})")
        elif t == "tool_result":
            notes.append("工具结果(略)")
        elif t == "image":
            notes.append("图片(略)")
        # reasoning / thinking: silently dropped
    return "\n".join(p for p in parts if p).strip(), notes


class Conv:
    def __init__(self, platform: str, conv_id: str):
        self.ir = {
            "schema_version": 1,
            "id": conv_id,
            "source": {"platform": platform, "conv_id": conv_id},
            "title": "",
            "created_at": "",
            "updated_at": "",
            "workspace": "",
            "models": [],
            "messages": [],   # {index, role, ts, text}
            "lossy_notes": [],
            "prebuilt_digest": "",
            "stats": {"msg_count": 0, "tokens_approx": 0},
        }
        self._dropped = {}

    def set_title(self, title: str, only_if_better=False):
        if not title:
            return
        if only_if_better and self.ir["title"] and len(title) <= len(self.ir["title"]):
            return
        self.ir["title"] = title.strip()

    def add_model(self, model: str):
        if model and model not in self.ir["models"]:
            self.ir["models"].append(model)

    def add_message(self, role: str, ts: str, text: str):
        if not text:
            return
        self.ir["messages"].append(
            {"index": len(self.ir["messages"]), "role": role, "ts": ts, "text": text}
        )
        if ts:
            if not self.ir["created_at"] or ts < self.ir["created_at"]:
                self.ir["created_at"] = ts
            if ts > self.ir["updated_at"]:
                self.ir["updated_at"] = ts

    def note(self, s: str):
        if s not in self.ir["lossy_notes"]:
            self.ir["lossy_notes"].append(s)

    def drop(self, kind: str, n: int = 1):
        self._dropped[kind] = self._dropped.get(kind, 0) + n

    def finalize(self):
        if self._dropped:
            self.note("跳过: " + ", ".join(f"{k}×{v}" for k, v in sorted(self._dropped.items())))
        self.ir["stats"]["msg_count"] = len(self.ir["messages"])
        self.ir["stats"]["tokens_approx"] = sum(approx_tokens(m["text"]) for m in self.ir["messages"])
        return self.ir


def ir_path(conv_id: str) -> Path:
    return config.IR_DIR / f"{conv_id}.json"


def save_ir(ir: dict) -> Path:
    config.IR_DIR.mkdir(parents=True, exist_ok=True)
    p = ir_path(ir["id"])
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(ir, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(p)
    return p


def merge_ir(ir: dict) -> str:
    """merge policy: newer updated_at wins; deterministic rerun is idempotent."""
    p = ir_path(ir["id"])
    if p.exists():
        try:
            old = json.loads(p.read_text(encoding="utf-8"))
            if old.get("updated_at", "") > ir.get("updated_at", ""):
                return "kept-old"
        except Exception:
            pass
    save_ir(ir)
    return "written"


def load_ir_all():
    out = []
    if config.IR_DIR.exists():
        for f in sorted(config.IR_DIR.glob("*.json")):
            try:
                out.append(json.loads(f.read_text(encoding="utf-8")))
            except Exception:
                pass
    out.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
    return out


def utf8_console():
    import sys
    for s in (sys.stdout, sys.stderr):
        if hasattr(s, "reconfigure"):
            s.reconfigure(encoding="utf-8", errors="replace")
