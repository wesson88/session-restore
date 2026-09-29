# session-restore (llh)

把散落在各 LLM / CLI agent 的会话蒸馏成可携带的「记忆包」——统一中间格式（IR），
在任何新会话、任何模型上注入即续聊。

> 设计与裁决记录见 vault：`20-知识/项目记录/会话记忆包/`
> **完整操作手册：`docs/operations.md`**（新机器接入 / 计划任务注册 / 日常动词 / 故障排查）

## 三个动词

```bash
python llh.py list     # 会话清单（新→旧）
python llh.py sync     # pull -> ingest(cc+dsh) -> commit -> push
python llh.py go       # sync + handoff 最新会话 -> CWD/CLAUDE.md + 剪贴板
python handoff.py <id|prefix|latest> --mode digest --clip   # 任意会话生成注入块
```

## 机器层 / 人机层

- **机器层**：`session-ssot` 私有仓库（IR JSON，一会话一文件）——只有本工具读写
- **人机层**：markdown 注入块（CLAUDE.md / 剪贴板）——人和 agent 读
- JSON 给机器，markdown 给人；谁也不用读谁的那份

## 配置（每台机器）

| 环境变量 | 默认 | 说明 |
|---|---|---|
| `LLH_SSOT_DIR` | `~/llm-history` | IR 存储目录（session-ssot 的本地克隆） |
| `LLH_CC_PROJECTS` | `~/.claude/projects` | CC 会话源 |
| `LLH_DSH_SESSIONS` | `~/.dsh/sessions` | DSH 会话源 |
| `LLH_HOME_TARGET` | `claude-code` | `go` 的默认注入目标 |

依赖：Python 3.10+，`pip install -r requirements.txt`（仅 zstandard）。

## 计划任务（傻瓜化）

```bat
schtasks /Create /TN "llh-sync" /TR "E:\workstation\ai\session-restore\llhsync.cmd" /SC MINUTE /MO 45 /F
schtasks /Create /TN "llh-go"  /TR "E:\workstation\ai\session-restore\llhgo.cmd"  /SC ONLOGON /F
```

公司侧每 45 分钟自动出境；家侧登录自动入境并把最新会话写进工作区 CLAUDE.md。

## 纪律

- 两周时间盒；kill 条件：两周后自己没用 → 停（见判例库）
- 轻损验收：N 问盲测召回率；核心指标 = 用 X% token 买回 Y% 保真
- 语言迁移点：v3 CLI 分发 → Rust（复用 txcript crate）；v3 MCP/插件 → TS。IR 与语言无关，重写零迁移
