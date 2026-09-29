# IR schema v1

一会话一文件：`<ssot>/ir/<conv_id>.json`，UTF-8，`ensure_ascii=false`。

```jsonc
{
  "schema_version": 1,
  "id": "session-56cfa3fe-...",           // = 源会话标识（dsh 目录名 / cc 文件名 stem）
  "source": { "platform": "dsh|claude-code", "conv_id": "..." },  // 幂等去重键
  "title": "...",                          // dsh: session/title(llm 优先) / cc: ai-title
  "created_at": "2026-09-29T10:00:00",     // ISO, 本地时区
  "updated_at": "2026-09-29T12:30:00",
  "workspace": "D:\\Markdown\\memory\\adam 或 munged bucket",
  "models": ["glm-5.3-flash"],             // dsh: request/header.config.model
  "messages": [
    { "index": 0, "role": "user|assistant", "ts": "...", "text": "纯文本" }
  ],
  "lossy_notes": ["工具调用 glob(...)", "跳过: reasoning-chunks×1789"],  // 诚实登记
  "prebuilt_digest": "...",                // cc: summary 行 / dsh: compact|checkpoint 事件
  "stats": { "msg_count": 42, "tokens_approx": 51000 }   // tokens ≈ len/4
}
```

## 合并策略

`updated_at` 新者胜；ingest 幂等（同源重跑结果确定），重复 sync 无副作用。

## 只存跨模型可迁移的最小公共集

纯文本消息为主。工具调用 → 一行摘要入 `lossy_notes`；图片/推理块/流式 chunk → 丢弃并计数。
转换要诚实：注入块里不允许出现静默空洞。

## 事件映射（实测 2026-09-29）

### DSH `session.jsonl.zstd`（zstd 压缩 JSONL 事件流）
- 保留：`session`(cwd/createdAt)、`user/message`、`assistant/message`(data.message.content)、
  `session/title`、`tool/call`(→lossy)、`request/header`(→models)、
  `*compact*|*checkpoint*`(→prebuilt_digest 候选)
- 丢弃：`assistant/chunk`、`reasoning-chunks`、`text-chunks`(流式增量，被完整消息取代)、
  `turn/*`、`step/*`、`permission/*`、`sandbox/*`、`approval/*`、`web/*`

### Claude Code `<uuid>.jsonl`（明文 JSONL）
- 保留：`user`(message.content, isMeta 跳过)、`assistant`(text 块 + tool_use→lossy)、
  `ai-title`(→title)、`summary`(→prebuilt_digest)、`attachment`(→lossy)
- 丢弃：mode / permission-mode / file-history-* / atis-latch / system / last-prompt

## 语言迁移点

IR 与语言无关。v3 重启时：CLI 分发→Rust（复用 txcript crate，Apache-2.0）；
MCP/插件→TS。Python 实现可直接退役，零迁移成本。
