"""llh: list / sync / go / probe

  python llh.py list            show IR conversations (newest first)
  python llh.py sync            pull -> ingest cc+dsh -> commit -> push
  python llh.py go              sync + handoff latest -> CLAUDE.md in CWD + clipboard
  python llh.py probe           count discoverable source sessions
"""
import subprocess
import sys

import common
from common import load_ir_all, utf8_console
import config


def sh(args, cwd=None, check=False, capture=False):
    return subprocess.run(args, cwd=cwd, check=check,
                          capture_output=capture, text=True,
                          encoding="utf-8", errors="replace")


def ensure_repo():
    config.SSOT_DIR.mkdir(parents=True, exist_ok=True)
    if not (config.SSOT_DIR / ".git").exists():
        sh(["git", "init"], cwd=config.SSOT_DIR)
        print(f"[git] initialized repo at {config.SSOT_DIR}")
    r = sh(["git", "remote"], cwd=config.SSOT_DIR, capture=True)
    if "origin" not in (r.stdout or ""):
        sh(["git", "remote", "add", "origin", config.SSOT_REMOTE], cwd=config.SSOT_DIR)
        print(f"[git] remote origin -> {config.SSOT_REMOTE}")


def git_pull():
    r = sh(["git", "pull", "--rebase"], cwd=config.SSOT_DIR, capture=True)
    print(f"[git] pull: {(r.stdout or r.stderr or '').strip()[:120]}")


def git_push():
    r = sh(["git", "push"], cwd=config.SSOT_DIR, capture=True)
    ok = r.returncode == 0
    print(f"[git] push: {'OK' if ok else (r.stderr or '').strip()[:200]}")
    return ok


def cmd_sync():
    ensure_repo()
    git_pull()
    import ingest_cc, ingest_dsh
    ingest_cc.main()
    ingest_dsh.main()
    sh(["git", "add", "-A"], cwd=config.SSOT_DIR)
    r = sh(["git", "diff", "--cached", "--quiet"], cwd=config.SSOT_DIR)
    if r.returncode != 0:
        sh(["git", "commit", "-m", f"llh sync {common.now_iso()}"], cwd=config.SSOT_DIR)
        print("[git] committed")
    else:
        print("[git] nothing new")
    git_push()


def cmd_go():
    cmd_sync()
    import handoff
    ir, _ = handoff.resolve_conv("latest")
    text = handoff.render_context(ir, "digest", 8, config.HOME_TARGET)
    handoff.save_handoff(ir, text)
    handoff.to_claude_md(common.Path(config.WORKSPACE).resolve(), text)
    handoff.set_clipboard(text)
    print(f"[go] latest conv: {ir['id'][:8]} {ir.get('title','')[:40]}")


def cmd_list():
    convs = load_ir_all()
    if not convs:
        print(f"no IR yet. run: python llh.py sync   (ir dir: {config.IR_DIR})")
        return
    print(f"{'#':>3}  {'date':10}  {'source':11}  {'msgs':>4}  {'~tok':>6}  title")
    for i, c in enumerate(convs, 1):
        print(f"{i:>3}  {c.get('updated_at','')[:10]:10}  {c['source']['platform']:11}  "
              f"{c['stats']['msg_count']:>4}  {c['stats']['tokens_approx']:>6}  {c.get('title','')[:46]}")


def cmd_probe():
    cc = list(config.CC_PROJECTS.glob("*/*.jsonl")) if config.CC_PROJECTS.exists() else []
    dsh = list(config.DSH_SESSIONS.glob("*/session-*/session.jsonl.zstd")) if config.DSH_SESSIONS.exists() else []
    print(f"cc sources : {len(cc):4}  ({config.CC_PROJECTS})")
    print(f"dsh sources: {len(dsh):4}  ({config.DSH_SESSIONS})")
    print(f"ir store   : {len(load_ir_all()):4}  ({config.IR_DIR})")


def main():
    utf8_console()
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "list":
        cmd_list()
    elif cmd == "sync":
        cmd_sync()
    elif cmd == "go":
        cmd_go()
    elif cmd == "probe":
        cmd_probe()
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
