from __future__ import annotations

import re

_ANSI_ESCAPE_RE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")


def _strip_ansi(text: str) -> str:
    return _ANSI_ESCAPE_RE.sub("", text or "")


def translate_error(error: BaseException) -> dict:
    """将异常对象转换为用户友好的错误字典。

    返回值尽量保持稳定的 keys：title/content/suggestion/raw_error。
    兼容老的 UI 代码的同时提供新的字段。
    """
    raw_original = str(error)
    # 检查是否是结构化的 YtDlpExecutionError
    from ..models.errors import YtDlpExecutionError
    from .error_parser import diagnose_error, generate_issue_url

    exit_code = 1
    if isinstance(error, YtDlpExecutionError):
        exit_code = error.exit_code
        raw_original = error.stderr

    raw = _strip_ansi(raw_original)

    diag = diagnose_error(exit_code, raw)
    friendly_title = diag.user_title
    friendly_content = diag.user_message

    issue_url = generate_issue_url(
        friendly_title if friendly_title != "解析或下载失败" else "发生未知错误", raw
    )

    result = {
        "title": friendly_title if friendly_title != "解析或下载失败" else "发生未知错误",
        "content": friendly_content,
        "suggestion": "1. 请重试\n2. 查看日志文件\n3. 将此错误反馈给开发者",
        "raw_error": raw,
        "issue_url": issue_url,
        "suggests_component_update": False,
        # 兼容新的 Diagnose 体系
        "code": diag.code.value,
        "severity": diag.severity,
        "user_title": friendly_title,
        "user_message": friendly_content,
        "fix_action": diag.fix_action,
        "technical_detail": diag.technical_detail,
        "recovery_hint": diag.recovery_hint,
    }

    if friendly_title != "解析或下载失败" and friendly_title != "发生未知错误":
        result["suggestion"] = ""

    return result
