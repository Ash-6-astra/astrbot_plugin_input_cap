# astrbot_plugin_input_cap

[![AstrBot](https://img.shields.io/badge/AstrBot-%E6%8F%92%E4%BB%B6-blue)](https://github.com/AstrBotDevs/AstrBot)
[![Version](https://img.shields.io/badge/version-0.1.0-green)]()
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**输入 Token 截断 / Input Token Cap** —— 一个轻量级 AstrBot LLM 插件：限制每次 LLM 请求的输入 Token 数量，超限时从最旧的上下文开始截断，防止上下文无限膨胀、控制 API 成本。

> A lightweight AstrBot plugin that caps the input tokens of each LLM request; when the limit is exceeded, the oldest context history is truncated first.

---

## ✨ 功能特性 | Features

- 🔒 **输入上限**：为单次 LLM 请求设置输入 Token 上限（不是每日用量上限）。
  - Set a hard cap on the input tokens of each single LLM request (not a daily quota).
- ✂️ **智能截断**：超过上限时，优先从**最旧的历史上下文**开始丢弃，并尽量保留最近 N 条消息与当前用户输入；`system_prompt` 永远不会被删除。
  - Truncates oldest history first, keeping the most recent N messages and the current user input; the system prompt is never removed.
- 🖼️ **多模态感知**：对图片内容块按可配置的固定成本估算 Token。
  - Estimates a configurable fixed cost for image blocks in multimodal input.
- 🈶 **中英混合友好**：内置估算器不依赖第三方 tokenizer——中文字符约 1 Token/字，英文/数字约 4 字符 1 Token，含少量协议开销。
  - Built-in estimator without third-party tokenizers: CJK ≈ 1 token per char, Latin/digits ≈ 4 chars per token, plus small per-message protocol overhead.
- 📉 **极端兜底**：若系统提示 + 当前输入本身就超过上限，会从**头部**截断当前 prompt（保留尾部最新内容）。
  - Fallback: if system prompt + current prompt alone exceed the limit, the head of the current prompt is trimmed (tail kept).
- 📜 **截断日志**：可选记录每次截断前后估算值，方便观察与调参。
  - Optional logging of estimated tokens before/after truncation.

## 🧠 工作原理 | How It Works

插件挂载在 `on_llm_request` 阶段（`priority=-9999`，最先执行），在实际调用 LLM 之前：

1. 估算 `system_prompt`、历史 `contexts`、当前 `prompt` 的总输入 Token；
2. 若超过 `max_input_tokens`，从最旧历史消息开始逐条丢弃，直至落入限额（至少保留 `min_keep_messages` 条最新消息）；
3. 若仍超限（系统提示 + 当前输入本身超限），按剩余预算从头部截断当前 `prompt`；
4. 可选输出一条截断日志，记录估算值变化。

The plugin hooks the earliest phase of `on_llm_request`, estimates input tokens, drops oldest history messages first when over budget, and finally trims the current prompt head if still over budget.

## 📦 安装 | Installation

### 方式一：AstrBot WebUI 导入

1. 下载本仓库的 ZIP（`Code ▾` → `Download ZIP`）或发行版附件；
2. 打开 AstrBot WebUI → **插件管理** → **从文件导入插件**，选择 ZIP；
3. 重载插件即生效。

### 方式二：手动安装

```bash
cd AstrBot/data/plugins
git clone https://github.com/<YOUR_USERNAME>/astrbot_plugin_input_cap.git
# 然后在 WebUI 中重载插件
```

> 要求 `astrbot_version >= 4.24.2`。无需额外 pip 依赖（不依赖第三方 tokenizer）。

## ⚙️ 配置 | Configuration

| 配置项 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `enabled` | bool | `true` | 启用插件 |
| `max_input_tokens` | int | `16000` | 单次请求输入 Token 上限；`0` 表示不限制 |
| `min_keep_messages` | int | `2` | 超限截断时至少保留的最新历史消息数 |
| `image_token_cost` | int | `1200` | 每个图片内容块的估算 Token 成本 |
| `log_truncation` | bool | `true` | 是否记录截断日志 |

配置项可在 WebUI → 插件管理 → 本插件 → **配置** 中直接修改。

### 调参建议 | Tuning Tips

- 建议从 `16000` 或 `20000` 开始测试，设置过低可能丢失较多上下文；
- 长人设/长系统提示的用户可适当调高；
- 图片较多时，可按实际模型视觉计费调整 `image_token_cost`。

## ⚠️ 注意事项 | Notes & Limitations

- 本插件是**保护性上限**，内置估算法与厂商 tokenizer 的精确计数存在偏差（无需本地 tokenizer，速度快、零依赖）；如需按供应商精确计费，请以官方账单为准。
- 本插件不负责**每日/累计 Token 用量**的统计与限额（那是另一类插件的职责）。
- 截断针对的是“发给模型的输入”，不会删除 AstrBot 本身的会话历史存储。

## 🧩 相关 | See Also

- [astrbot_plugin_token_controller](https://github.com/) —— 用户级 Token 用量统计与限额。

## 📄 License

[MIT](LICENSE) © luoyuan
