"""限制每次 LLM 请求的输入 Token；超限时截断最旧上下文。"""

from __future__ import annotations

import math
from typing import Any

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.provider import ProviderRequest
from astrbot.api.star import Context, Star, register


_CJK_RANGES = (
    (0x3400, 0x4DBF),
    (0x4E00, 0x9FFF),
    (0xF900, 0xFAFF),
)


def _is_cjk(ch: str) -> bool:
    code = ord(ch)
    return any(start <= code <= end for start, end in _CJK_RANGES)


def _estimate_text(text: Any) -> int:
    if text is None:
        return 0
    text = str(text)
    if not text:
        return 0
    cjk = sum(1 for ch in text if _is_cjk(ch))
    other = len(text) - cjk
    return cjk + math.ceil(other / 4)


def _estimate_content(content: Any, image_cost: int) -> int:
    if content is None:
        return 0
    if isinstance(content, str):
        return _estimate_text(content)
    if isinstance(content, list):
        total = 0
        for part in content:
            if isinstance(part, str):
                total += _estimate_text(part)
                continue
            if not isinstance(part, dict):
                total += _estimate_text(part)
                continue
            kind = str(part.get("type", ""))
            if kind in {"image_url", "image", "input_image"}:
                total += image_cost
            elif kind in {"text", "input_text"}:
                total += _estimate_text(part.get("text", ""))
            else:
                total += _estimate_text(part)
        return total
    return _estimate_text(content)


def _estimate_message(message: Any, image_cost: int) -> int:
    if not isinstance(message, dict):
        return _estimate_text(message)
    # 给 role/name 留一点协议开销，避免估算过于乐观。
    return 4 + _estimate_content(message.get("content", ""), image_cost)


@register(
    "astrbot_plugin_input_cap",
    "luoyuan",
    "限制每次 LLM 请求输入 Token，超限时截断最旧上下文",
    "0.1.0",
)
class InputCapPlugin(Star):
    def __init__(self, context: Context, config: dict | None = None):
        super().__init__(context)
        self.config = config if isinstance(config, dict) else {}

    def _int_config(self, key: str, default: int) -> int:
        try:
            return int(self.config.get(key, default))
        except (TypeError, ValueError):
            return default

    @filter.on_llm_request(priority=-9999)
    async def cap_input(self, event: AstrMessageEvent, req: ProviderRequest) -> None:
        if self.config.get("enabled", True) is False:
            return

        limit = self._int_config("max_input_tokens", 16000)
        if limit <= 0:
            return
        image_cost = max(0, self._int_config("image_token_cost", 1200))
        keep = max(0, self._int_config("min_keep_messages", 2))

        system_tokens = _estimate_text(getattr(req, "system_prompt", ""))
        prompt_tokens = _estimate_text(getattr(req, "prompt", ""))
        contexts = list(getattr(req, "contexts", None) or [])
        context_tokens = sum(_estimate_message(item, image_cost) for item in contexts)
        before = system_tokens + prompt_tokens + context_tokens

        if before <= limit:
            return

        # 当前输入和系统提示不主动删除；历史从最旧消息开始丢弃。
        removable = max(0, len(contexts) - keep)
        removed = 0
        while before > limit and removed < removable:
            before -= _estimate_message(contexts[removed], image_cost)
            removed += 1

        if removed:
            req.contexts = contexts[removed:]

        # 极端情况下，系统提示+当前输入本身就超过上限，只能截当前 prompt。
        after = system_tokens + prompt_tokens + sum(
            _estimate_message(item, image_cost) for item in (getattr(req, "contexts", None) or [])
        )
        if after > limit and getattr(req, "prompt", None):
            budget = max(0, limit - system_tokens - sum(
                _estimate_message(item, image_cost)
                for item in (getattr(req, "contexts", None) or [])
            ))
            prompt = str(req.prompt)
            # 以字符为单位从前面保留尾部，避免破坏当前最新内容。
            if budget <= 0:
                req.prompt = ""
            else:
                approx_chars = max(1, budget * 2)
                req.prompt = prompt[-approx_chars:]
            after = system_tokens + _estimate_text(req.prompt) + sum(
                _estimate_message(item, image_cost)
                for item in (getattr(req, "contexts", None) or [])
            )

        if self.config.get("log_truncation", True):
            logger.info(
                "InputCap truncated LLM input: estimated %s -> %s tokens, "
                "limit=%s, removed_context_messages=%s",
                before if removed == 0 else system_tokens + prompt_tokens + context_tokens,
                after,
                limit,
                removed,
            )
