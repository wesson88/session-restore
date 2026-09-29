"""ingest Claude Code sessions (~/.claude/projects/<bucket>/<uuid>.jsonl) -> IR.

Observed line types: user, assistant, attachment, ai-title, mode,
permission-mode, file-history-snapshot, system, summary, last-prompt, ...
We keep user/assistant text, ai-title as title, summary as prebuilt_digest;
everything else is counted as dropped.
"""
import json
import sys
from pathlib import Path

import common
from common import Conv, text_from_content, merge_ir, utf8_console
import config


def parse_file(f: Path) -> Conv:
    conv_id = f.stem
    conv = Conv("claude-code", conv_id)
    conv.ir["workspace"] = f.parent.name  # munged path bucket
    try:
        raw = f.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        conv.drop(f"unreadable({e})")
        return conv
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            o = json.loads(line)
        except Exception:
            conv.drop("PARSE-ERR")
            continue
        t = o.get("type")
        if t == "user":
            if o.get("isMeta"):
                conv.drop("user-meta")
                continue
            msg = o.get("message", {}) or {}
            text, notes = text_from_content(msg.get("content"))
            for n in notes:
                conv.note(n)
            conv.add_message("user", o.get("timestamp", ""), text)
        elif t == "assistant":
            msg = o.get("message", {}) or {}
            blocks = msg.get("content")
            text, notes = text_from_content(blocks)
            for n in notes:
                conv.note(n)
            conv.add_message("assistant", o.get("timestamp", ""), text)
        elif t == "ai-title":
            conv.set_title(o.get("title", ""))
        elif t == "summary":
            s = o.get("summary", "")
            if s and not conv.ir["prebuilt_digest"]:
                conv.ir["prebuilt_digest"] = s  # CC compaction summary
        elif t in ("attachment",):
            conv.note("附件(略)")
        else:
            conv.drop(str(t))
    if not conv.ir["title"]:  # fallback: first user message
        for m in conv.ir["messages"]:
            if m["role"] == "user":
                conv.set_title(m["text"][:50])
                break
    return conv


def main():
    utf8_console()
    if not config.CC_PROJECTS.exists():
        print(f"[cc] no projects dir: {config.CC_PROJECTS}")
        return
    n_new = n_kept = 0
    for f in sorted(config.CC_PROJECTS.glob("*/*.jsonl")):
        try:
            ir = parse_file(f).finalize()
        except Exception as e:
            print(f"[cc] FAIL {f.name}: {e}")
            continue
        if ir["stats"]["msg_count"] == 0 and not ir["title"]:
            continue  # empty/noise session
        r = merge_ir(ir)
        if r == "written":
            n_new += 1
        else:
            n_kept += 1
    print(f"[cc] written={n_new} kept-old={n_kept}")


if __name__ == "__main__":
    main()
