# 会话记忆包 操作手册（operations）

> 心智图三行：公司/生产机自动出境，家/消费机登录自动入境，GitHub 私库是唯一交汇点。
> 你的必做动作 = **0 步**；手动动词只用于急切切换和异常处理。

---

## 1. 新机器接入（约 10 分钟，一次性）

前置：git、Python 3.10+（家机器若跑 DSH 还需 `pip install zstandard`，只当消费端则不需要）。

```bat
git clone https://github.com/wesson88/session-restore  <代码目录>
git clone https://github.com/wesson88/session-ssot     <数据目录>
cd <代码目录>
pip install -r requirements.txt
setx LLH_SSOT_DIR <数据目录绝对路径>
```

验证（**setx 后必须重开终端**）：

```bat
python llh.py probe    &rem 三个数字：cc 源数 / dsh 源数 / ir 数
python llh.py sync     &rem 首次会把本机会话全量蒸馏并推送
python llh.py list     &rem 应能看到两台机器的会话
```

## 2. 计划任务注册

**生产机（公司 DSH）**——每 45 分钟自动出境，睡眠唤醒后补跑：

```powershell
$a = New-ScheduledTaskAction -Execute "<代码目录>\llhsync.cmd"
$t = New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Minutes 45) -RepetitionDuration (New-TimeSpan -Days 3650)
$s = New-ScheduledTaskSettingsSet -StartWhenAvailable -WakeToRun -ExecutionTimeLimit (New-TimeSpan -Minutes 10)
Register-ScheduledTask -TaskName "llh-sync" -Action $a -Trigger $t -Settings $s -Force
```

**消费机（家 CC）**——登录自动入境：

```powershell
$a = New-ScheduledTaskAction -Execute "<代码目录>\llhgo.cmd" -WorkingDirectory "<家工作区>"
$t = New-ScheduledTaskTrigger -AtLogOn
Register-ScheduledTask -TaskName "llh-go" -Action $a -Trigger $t -Force
```

删除：`Unregister-ScheduledTask -TaskName "llh-sync" -Confirm:$false`

⚠️ **`go` 的 CLAUDE.md 落点 = `LLH_WORKSPACE`**（`setx LLH_WORKSPACE <家工作区>`）。不配则落在进程 CWD——计划任务里那是 System32，等于丢进黑洞。

## 3. 日常动词（全部）

| 场景 | 命令 | 步数 |
|---|---|---|
| 看库里有什么 | `python llh.py list` | 1 |
| 急着出境（不等 45min） | 双击/跑 `llhsync.cmd` | 1 |
| 家里入境最新会话 | 跑 `llhgo.cmd`（或等登录任务） | 0–1 |
| 续指定会话（非最新） | `python llh.py list` → `python handoff.py <id前缀> --mode digest --clip` | 2 |
| 要全文不要摘要 | 上述命令加 `--mode full` | — |
| 注入到指定工作区 | `--to-claude-md <工作区路径>`（幂等替换标记区） | — |
| 健康检查 | `python llh.py probe` | 1 |

## 4. CLAUDE.md 注入机制

`--to-claude-md` / `go` 只写入并幂等替换这对标记之间的内容，不碰文件其他部分：

```
<!-- llh:handoff:start -->
…注入块（身份头 + 早期摘要 + 最近 8 条原文 + lossy 说明）…
<!-- llh:handoff:end -->
```

CC 在该工作区开会话即自动加载。不想自动加载就用 `--clip` 纯剪贴板。

## 5. 一致性模型速记

- 会话文件**属主唯一**（在哪台机产生只有那台机改写）→ 写集不相交 → git 永不冲突；
- **续聊 = 派生新会话**（新文件），不是共写旧会话——分叉显式化，合并 = 再来一次 handoff；
- 同会话多批次出境：`updated_at` 新者胜，系统永远收敛到最新快照；
- 收敛口径：**每台机器本地 = 上次 sync 的全局并集快照，延迟 ≤45min（或唤醒后立即）**。

## 6. 故障排查表

| 症状 | 诊断 | 处置 |
|---|---|---|
| `no IR found at ...` | LLH_SSOT_DIR 没配，或还没 sync 过 | `setx LLH_SSOT_DIR` 后**重开终端**；先跑 `sync` |
| push 403 / 要求认证 | GitHub 凭据过期 | 凭据管理器重新登录 GitHub，或换 PAT |
| 新会话不在 list 里 | 源路径不对 / 会话为空被跳过 | `python llh.py probe` 核对两个源数字；空会话（0 消息）本来就不入库 |
| sync 报 zstd 相关错 | 缺依赖 | `pip install zstandard` |
| 标题是空的 | CC 老会话无 ai-title | 正常，已回退「首条用户消息」；可用 `--to-claude-md` 前先 `list` 认前缀 |
| 控制台中文乱码 | 老控制台 GBK | 文件均为 UTF-8 不受影响；介意则 `chcp 65001` |
| 睡眠后好像漏了一次 | 任务默认不补 | 用 §2 的 `-StartWhenAvailable` 版本注册 |

## 7. 隐私与合规

- `session-ssot` 为**私有**仓库；公司内容出境的两条自查（push 权限、内容出边界）立项时已确认通过；
- 敏感机器可整体换通道：`setx LLH_SSOT_REMOTE <内部Git或坚果云同步目录的remote>`，pipeline 不变；
- 公司→家方向若日后需要脱敏：只用 `--mode digest`（只导决策/结论，不含代码原文原文）。

## 8. v1 已知限制

- 出境粒度 45min（手动 `llhsync` 可即时）；digest 有损（用抽查协议量化，见总览 §4.3）；
- CC/DSH 改存储格式需补丁解析器（映射表见 `docs/schema-v1.md`，外部参考：txcript `docs/formats/`）；
- 无 UI、无实时监听、无自动摘要 API（digest 为抽取式，递归摘要属 v2）。
