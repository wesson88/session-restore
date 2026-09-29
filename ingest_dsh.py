"""ingest DeepSeek Harness sessions (~/.dsh/sessions/<bucket>/<uuid>/session.jsonl.zstd) -> IR.

Observed event types: session, permission/*, sandbox/*, approval/*,
agent/inbox/spliced, turn/*, step/*, user/message, assistant/message,
assistant/chunk, reasoning-chunks, text-chunks, tool/call, tool/result,
session/title, session/title-llm-request, request/header, request/context,
web/*.  We keep user/assistant full messages, session/title, tool/call as
lossy notes, model hints from request/header; streaming chunks are dropped.
"""
import io
import json
import sys
from pathlib import Path

from common import Conv, text_from_content, merge_ir, ms_to_iso, utf8_console
import config


def parse_file(f: Path) -> Conv:
    import zstandard

    conv_id = f.parent.name  # session-<uuid>
    conv = Conv("dsh", conv_id)
    conv.ir["workspace"] = f.parent.parent.name  # munged cwd bucket
    n_stream = 0
    with zstandard.open(f, "rb") as zr:
        for raw in io.TextIOWrapper(zr, encoding="utf-8", errors="replace"):
            line = raw.strip()
            if not line:
                continue
            try:
                o = json.loads(line)
            except Exception:
                conv.drop("PARSE-ERR")
                continue
            t = str(o.get("type", ""))
            d = o.get("data", {}) or {}
            ts = ms_to_iso(o.get("time"))
            if t == "session":
                conv.ir["workspace"] = d.get("cwd", "") or conv.ir["workspace"]
                if not conv.ir["created_at"]:
                    conv.ir["created_at"] = ms_to_iso(d.get("createdAt"))
            elif t == "user/message":
                text, notes = text_from_content(d.get("content"))
                for n in notes:
                    conv.note(n)
                conv.add_message("user", ts, text)
            elif t == "assistant/message":
                msg = d.get("message", {}) or {}
                blocks = msg.get("content")
                text, notes = text_from_content(blocks)
                for n in notes:
                    conv.note(n)
                conv.add_message("assistant", ts, text)
            elif t in ("reasoning-chunks", "text-chunks", "assistant/chunk"):
                n_stream += 1  # streaming deltas, superseded by assistant/message
            elif t == "tool/call":
                conv.note(f"工具调用 {d.get('name', 'tool')}")
            elif t == "tool/result":
                conv.note("工具结果(略)")
            elif t == "session/title":
                # prefer llm titles over fallback (first-prompt truncation)
                conv.set_title(d.get("title", ""), only_if_better=(d.get("source", {}).get("kind") == "fallback"))
            elif t == "request/header":
                try:
                    conv.add_model(d.get("header", {}).get("config", {}).get("model", ""))
                except Exception:
                    pass
            elif "compact" in t or "checkpoint" in t:
                if not conv.ir["prebuilt_digest"]:
                    txt = ""
                    s = d.get("summary")
                    if isinstance(s, list):
                        txt, _ = text_from_content(s)
                    elif isinstance(s, str):
                        txt = s
                    elif isinstance(d.get("text"), str):
                        txt = d["text"]
                    if txt and len(txt) > 100:
                        conv.ir["prebuilt_digest"] = txt[:6000]
                conv.note(f"压缩/检查点事件 {t}(已存为早期摘要)")
            else:
                conv.drop(t or "NO-TYPE")
    if n_stream:
        conv.drop("流式chunk(被完整消息取代)", n_stream)
    return conv


def main():
    utf8_console()
    if not config.DSH_SESSIONS.exists():
        print(f"[dsh] no sessions dir: {config.DSH_SESSIONS}")
        return
    n_new = n_kept = 0
    for f in sorted(config.DSH_SESSIONS.glob("*/session-*/session.jsonl.zstd")):
        try:
            ir = parse_file(f).finalize()
        except Exception as e:
            print(f"[dsh] FAIL {f.parent.name}: {e}")
            continue
        if ir["stats"]["msg_count"] == 0 and not ir["title"]:
            continue
        r = merge_ir(ir)
        if r == "written":
            n_new += 1
        else:
            n_kept += 1
    print(f"[dsh] written={n_new} kept-old={n_kept}")


if __name__ == "__main__":
    main()
