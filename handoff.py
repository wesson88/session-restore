"""handoff: render an IR conversation into a paste-ready context block.

usage:
  python handoff.py <conv_id|prefix|latest> [--mode full|digest] [--k 8]
      [--out FILE] [--clip] [--to-claude-md [WORKSPACE]]

  --mode full    inject whole conversation verbatim
  --mode digest  last K messages verbatim + earlier part summarized/truncated
  --target       claude-code|dsh  (affects the trailing instruction wording)
"""
import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import common
from common import load_ir_all, utf8_console
import config

MARK_BEGIN = "<!-- llh:handoff:start -->"
MARK_END = "<!-- llh:handoff:end -->"


def resolve_conv(key: str):
    convs = load_ir_all()
    if not convs:
        print(f"no IR found at {config.IR_DIR}")
        print("hint: set LLH_SSOT_DIR / run 'python llh.py sync' first")
        sys.exit(1)
    if key in ("", "latest"):
        return convs[0], convs
    for c in convs:  # exact id
        if c["id"] == key:
            return c, convs
    hits = [c for c in convs if c["id"].startswith(key)]
    if len(hits) == 1:
        return hits[0], convs
    if len(hits) > 1:
        print(f"ambiguous prefix '{key}', {len(hits)} matches; use more chars")
        sys.exit(2)
    # try title substring
    hits = [c for c in convs if key.lower() in c.get("title", "").lower()]
    if len(hits) == 1:
        return hits[0], convs
    print(f"no conversation matches '{key}'")
    sys.exit(2)


def _fmt_msg(m):
    return f"[{m['role']}] {m['text']}"


def render_context(ir: dict, mode: str = "digest", k: int = 8, target: str = "claude-code") -> str:
    msgs = ir.get("messages", [])
    src = ir["source"]["platform"]
    date = ir.get("created_at", "")[:10]
    turns = ir["stats"]["msg_count"]
    lines = [
        f'<context_block source="{src}" conv="{ir["id"][-8:]}" date="{date}" turns="{turns}">',
    ]
    head = (
        "以下是我们在另一个工具中的对话记录。请将其视为你与我共同的历史，"
        "不要复述、不要评价，直接在此基础上一继续聊。"
        if target == "claude-code"
        else "以下是我们在其他工具中的对话记录，请视为共同历史，直接续聊。"
    )
    lines.append(head)
    lines.append("")
    tail = msgs[-k:] if mode == "digest" and len(msgs) > k else msgs
    earlier = msgs[:-k] if mode == "digest" and len(msgs) > k else []
    if earlier:
        pd = ir.get("prebuilt_digest", "")
        if pd:
            lines.append("【早期部分·摘要】")
            lines.append(pd[:3000])
        else:
            lines.append("【早期部分·节选】(每条仅保留开头)")
            for m in earlier:
                t = m["text"]
                t = t[:160] + ("…" if len(t) > 160 else "")
                lines.append(f"[{m['role']}] {t}")
        lines.append("")
        lines.append("【最近原文】")
    for m in tail:
        lines.append(_fmt_msg(m))
    if ir.get("lossy_notes"):
        lines.append("")
        lines.append("(转换说明: " + "; ".join(ir["lossy_notes"][:6]) + ")")
    lines.append("</context_block>")
    return "\n".join(lines)


def save_handoff(ir: dict, text: str) -> Path:
    config.HANDOFF_DIR.mkdir(parents=True, exist_ok=True)
    p = config.HANDOFF_DIR / f"{ir['id']}.md"
    p.write_text(text, encoding="utf-8")
    return p


def set_clipboard(text: str):
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".txt", delete=False) as f:
        f.write(text)
        tmp = f.name
    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             f"Get-Content -Raw -Encoding UTF8 '{tmp}' | Set-Clipboard"],
            check=True, capture_output=True,
        )
        print("clipboard: OK")
    except Exception as e:
        print(f"clipboard: FAILED ({e}); content also saved to file")
    finally:
        Path(tmp).unlink(missing_ok=True)


def to_claude_md(workspace: Path, text: str):
    md = workspace / "CLAUDE.md"
    if md.exists():
        old = md.read_text(encoding="utf-8", errors="replace")
        b, s, e = old.find(MARK_BEGIN), MARK_BEGIN, MARK_END
        if b != -1 and s in old and e in old:
            new = old[: old.find(s)] + s + "\n" + text + "\n" + e + old[old.find(e) + len(e):]
        else:
            new = old.rstrip() + "\n\n" + s + "\n" + text + "\n" + e + "\n"
    else:
        new = s + "\n" + text + "\n" + e + "\n"
    md.write_text(new, encoding="utf-8")
    print(f"CLAUDE.md updated: {md}")


def main():
    utf8_console()
    ap = argparse.ArgumentParser()
    ap.add_argument("conv", nargs="?", default="latest")
    ap.add_argument("--mode", choices=["full", "digest"], default="digest")
    ap.add_argument("--k", type=int, default=8)
    ap.add_argument("--target", choices=["claude-code", "dsh"], default=config.HOME_TARGET)
    ap.add_argument("--out")
    ap.add_argument("--clip", action="store_true")
    ap.add_argument("--to-claude-md", nargs="?", const=".", default=None)
    a = ap.parse_args()

    ir, _ = resolve_conv(a.conv)
    text = render_context(ir, a.mode, a.k, a.target)
    saved = save_handoff(ir, text)
    print(f"conv: {ir['id']}  title: {ir.get('title','')[:40]}  msgs: {ir['stats']['msg_count']}")
    print(f"mode={a.mode} target={a.target}  saved: {saved}")
    if a.out:
        Path(a.out).write_text(text, encoding="utf-8")
        print(f"out: {a.out}")
    if a.to_claude_md is not None:
        to_claude_md(Path(a.to_claude_md).resolve(), text)
    if a.clip:
        set_clipboard(text)
    if not (a.clip or a.out or a.to_claude_md):
        print("\n" + text)


if __name__ == "__main__":
    main()
