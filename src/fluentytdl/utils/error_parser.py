import re
from typing import Any

from ..models.errors import DiagnosedError, ErrorCode

# ==================== 翻译与字典 ====================
HTTP_STATUS_TRANSLATIONS = {
    400: "请求格式错误 (Bad Request)",
    401: "需要身份验证 (Unauthorized)",
    403: "访问被拒绝 (Forbidden)",
    404: "页面/资源不存在 (Not Found)",
    410: "资源已永久删除 (Gone)",
    412: "前提条件失败 (Precondition Failed)",
    429: "请求过于频繁 (Too Many Requests)",
    500: "服务器内部错误 (Internal Server Error)",
    502: "网关错误 (Bad Gateway)",
    503: "服务暂时不可用 (Service Unavailable)",
    504: "网关超时 (Gateway Timeout)",
}

EXTRACTOR_NAMES = {
    "youtube": "YouTube",
    "bilibili": "哔哩哔哩",
    "twitter": "X (Twitter)",
    "niconico": "NicoNico",
    "twitch": "Twitch",
    "tiktok": "抖音/TikTok",
    "instagram": "Instagram",
    "facebook": "Facebook",
    "vimeo": "Vimeo",
}

# ==================== 错误匹配规则引擎 ====================
ERROR_RULES = [
    # ---- 认证与权限 ----
    {
        "condition": "regex",
        "value": r"Sign in to confirm you're not a bot|Sign in to confirm youre not a bot|Error solving n challenge|poToken",
        "error_code": ErrorCode.POTOKEN_FAILURE,
        "severity": "fatal",
        "fix_action": "switch_proxy",
        "title": "人机验证拦截 (Bot 检测)",
        "message": "服务提供商认为当前请求来自自动化工具。这通常是因为节点 IP 触发了风控，或者 Cookie 被限制。",
        "recovery_hint": "更换代理节点",
    },
    {
        "condition": "regex",
        "value": r"Members only content|Join this channel to get access",
        "error_code": ErrorCode.LOGIN_REQUIRED,
        "severity": "fatal",
        "fix_action": "extract_cookie",
        "title": "会员专属视频",
        "message": "这是频道的会员专享内容，请确保使用的 Cookie 关联的账号已购买该频道会员。",
        "recovery_hint": "重新导入 Cookie",
    },
    {
        "condition": "regex",
        "value": r"Sign in to confirm your age",
        "error_code": ErrorCode.LOGIN_REQUIRED,
        "severity": "fatal",
        "fix_action": "extract_cookie",
        "title": "年龄限制 (需要登录验证)",
        "message": "该视频有年龄限制，必须使用已验证年龄的账号才能访问。",
        "recovery_hint": "导入 Cookie",
    },
    {
        "condition": "regex",
        "value": r"Private video|This video is only available to registered users",
        "error_code": ErrorCode.LOGIN_REQUIRED,
        "severity": "fatal",
        "fix_action": "extract_cookie",
        "title": "私人视频",
        "message": "该视频已被上传者设置为私有，必须拥有观看权限的账号才能访问。",
        "recovery_hint": "导入 Cookie",
    },
    {
        "condition": "regex",
        "value": r"Sign in to confirm|login required|requires authentication",
        "error_code": ErrorCode.LOGIN_REQUIRED,
        "severity": "fatal",
        "fix_action": "extract_cookie",
        "title": "需要登录验证",
        "message": "网站要求您登录以确认身份。可能是 Cookie 缺失/已失效，或者遇到了权限验证。",
        "recovery_hint": "导入 Cookie",
    },
    # ---- 视频状态 ----
    {
        "condition": "regex",
        "value": r"This video has been removed|Video unavailable",
        "error_code": ErrorCode.VIDEO_REMOVED,
        "severity": "fatal",
        "fix_action": None,
        "title": "视频已失效/被删除",
        "message": "该视频已被平台或上传者删除，无法继续下载。",
        "recovery_hint": "",
    },
    {
        "condition": "regex",
        "value": r"This live event has ended|This live stream",
        "error_code": ErrorCode.LIVE_STREAM,
        "severity": "fatal",
        "fix_action": None,
        "title": "直播状态异常",
        "message": "该内容是直播流或已结束的直播，当前暂无法直接提取。",
        "recovery_hint": "",
    },
    {
        "condition": "regex",
        "value": r"Premiere",
        "error_code": ErrorCode.GENERAL,
        "severity": "fatal",
        "fix_action": None,
        "title": "首映未开始",
        "message": "该视频属于首映状态，尚未正式开启播放或您没有观看权限。",
        "recovery_hint": "",
    },
    {
        "condition": "regex",
        "value": r"is not a valid URL|Incomplete YouTube ID|Unsupported URL",
        "error_code": ErrorCode.URL_INVALID,
        "severity": "fatal",
        "fix_action": None,
        "title": "链接无效或不支持",
        "message": "提供的链接格式不正确，或者当前组件不支持解析该网站。",
        "recovery_hint": "",
    },
    {
        "condition": "regex",
        "value": r"No video formats found|no video results",
        "error_code": ErrorCode.FORMAT_UNAVAILABLE,
        "severity": "fatal",
        "fix_action": None,
        "title": "无可用流媒体格式",
        "message": "在该页面未找到可供下载的音视频流数据。",
        "recovery_hint": "",
    },
    {
        "condition": "regex",
        "value": r"Requested format is not available",
        "error_code": ErrorCode.FORMAT_UNAVAILABLE,
        "severity": "warning",
        "fix_action": None,
        "title": "无可用视频流",
        "message": "指定的画质、音质或格式在当前视频中不存在。",
        "recovery_hint": "",
    },
    # ---- 核心组件/提取错误 ----
    {
        "condition": "regex",
        "value": r"unable to extract|no suitable InfoExtractor",
        "error_code": ErrorCode.EXTRACTOR_ERROR,
        "severity": "fatal",
        "fix_action": None,
        "title": "提取器失败",
        "message": "解析该网页内容时失败。可能是目标网站改版，建议更新解析核心组件。",
        "recovery_hint": "",
    },
    {
        "condition": "regex",
        "value": r"ffprobe/ffmpeg not found|ffmpeg isn't installed",
        "error_code": ErrorCode.GENERAL,
        "severity": "fatal",
        "fix_action": None,
        "title": "缺少核心组件 (FFmpeg)",
        "message": "视频合并或封面处理需要 FFmpeg，但系统未找到该工具。",
        "recovery_hint": "",
    },
    # ---- 网络连接错误 ----
    {
        "condition": "regex",
        "value": r"Connection reset by peer|Connection refused|Connection timed out|Read timed out|Timed out|WinError 10060",
        "error_code": ErrorCode.NETWORK_ERROR,
        "severity": "recoverable",
        "fix_action": "switch_proxy",
        "title": "网络连接超时或被拒绝",
        "message": "无法与目标服务器建立连接，通常是网络环境或代理节点问题。",
        "recovery_hint": "检查代理设置",
    },
    {
        "condition": "regex",
        "value": r"CERTIFICATE_VERIFY_FAILED|ssl\.SSLCertVerificationError|certificate verify failed",
        "error_code": ErrorCode.NETWORK_ERROR,
        "severity": "recoverable",
        "fix_action": "switch_proxy",
        "title": "SSL 证书验证失败",
        "message": "HTTPS 连接被干扰，证书无法通过验证。可能是代理软件篡改了证书或网络被劫持。",
        "recovery_hint": "检查代理配置",
    },
    {
        "condition": "regex",
        "value": r"urlopen error|URLError|Name or service not known|getaddrinfo failed|Errno 11001|Temporary failure in name resolution",
        "error_code": ErrorCode.NETWORK_ERROR,
        "severity": "recoverable",
        "fix_action": "switch_proxy",
        "title": "DNS 解析失败",
        "message": "无法解析目标域名，通常是 DNS 被污染或网络不通。",
        "recovery_hint": "检查网络或代理",
    },
    {
        "condition": "regex",
        "value": r"proxy|ProxyError|Cannot connect to proxy|SOCKSHTTPSConnectionPool|WinError 10061",
        "error_code": ErrorCode.NETWORK_ERROR,
        "severity": "recoverable",
        "fix_action": "switch_proxy",
        "title": "代理连接失败",
        "message": "无法连接到配置的代理服务器。",
        "recovery_hint": "检查代理设置",
    },
    # ---- HTTP 错误 ----
    {
        "condition": "regex",
        "value": r"HTTP Error 429|Too Many Requests",
        "error_code": ErrorCode.RATE_LIMITED,
        "severity": "recoverable",
        "fix_action": "switch_proxy",
        "title": "请求频率过高 (429 限流)",
        "message": "短时间内请求过多，被临时限流保护。通常在停止请求后的 2-12 小时内会自动恢复。",
        "recovery_hint": "更换节点/稍后重试",
    },
    {
        "condition": "regex",
        "value": r"HTTP Error 403|forbidden",
        "error_code": ErrorCode.HTTP_ERROR,
        "severity": "fatal",
        "fix_action": "switch_proxy",
        "title": "IP/节点被风控 (403)",
        "message": "服务器拒绝了请求。通常是因为代理节点 IP 被临时封锁，与组件版本无关。",
        "recovery_hint": "更换代理节点",
    },
    {
        "condition": "regex",
        "value": r"Video unavailable in your country|Geo-restricted",
        "error_code": ErrorCode.GEO_RESTRICTED,
        "severity": "fatal",
        "fix_action": "switch_proxy",
        "title": "地区限制",
        "message": "由于版权或区域限制，当前网络节点无法访问该内容。",
        "recovery_hint": "更换代理节点",
    },
    # ---- 系统读写错误 ----
    {
        "condition": "regex",
        "value": r"No space left on device|Disk quota exceeded",
        "error_code": ErrorCode.DISK_FULL,
        "severity": "fatal",
        "fix_action": "open_settings",
        "title": "磁盘空间不足",
        "message": "当前下载目录所在的分区没有足够的剩余空间。",
        "recovery_hint": "清理磁盘/更换路径",
    },
    {
        "condition": "regex",
        "value": r"File name too long",
        "error_code": ErrorCode.FILE_SYSTEM_ERROR,
        "severity": "fatal",
        "fix_action": None,
        "title": "文件名过长",
        "message": "视频标题生成的文件名超过了系统限制长度，无法写入磁盘。",
        "recovery_hint": "",
    },
    {
        "condition": "regex",
        "value": r"Permission denied|WinError 5",
        "error_code": ErrorCode.FILE_SYSTEM_ERROR,
        "severity": "fatal",
        "fix_action": None,
        "title": "文件权限不足",
        "message": "没有足够的系统权限在当前目录写入或创建文件。",
        "recovery_hint": "更换下载路径",
    },
    {
        "condition": "regex",
        "value": r"IncompleteRead|ContentTooShortError",
        "error_code": ErrorCode.DOWNLOAD_INTERRUPTED,
        "severity": "recoverable",
        "fix_action": None,
        "title": "下载意外中断",
        "message": "数据传输过程中意外断开连接。",
        "recovery_hint": "重试下载",
    },
]


def diagnose_error(
    exit_code: int, stderr: str, parsed_json: dict[str, Any] | None = None
) -> DiagnosedError:
    """
    核心诊断函数：根据退出码、错误输出和 JSON 结构，生成诊断对象。
    """
    if not stderr:
        stderr = "未知错误，无输出"

    clean_msg = " ".join(stderr.splitlines())

    # 1. JSON 层级判断（如果有传入解析好的 JSON 错误快照，未来可扩展）
    if parsed_json and isinstance(parsed_json, dict):
        err_type = parsed_json.get("error", {}).get("_type")
        if err_type == "premium_only":
            return DiagnosedError(
                code=ErrorCode.LOGIN_REQUIRED,
                severity="fatal",
                user_title="会员专属视频",
                user_message="这是会员专享内容，请确保账号已购买频道会员。",
                fix_action="extract_cookie",
                technical_detail=f"exit_code={exit_code}, json_error={err_type}",
                recovery_hint="导入 Cookie",
            )

    # 2. 启发式文本/正则层级判断
    for rule in ERROR_RULES:
        if rule.get("condition") == "regex":
            if re.search(rule["value"], clean_msg, re.IGNORECASE):
                return DiagnosedError(
                    code=rule["error_code"],
                    severity=rule["severity"],  # type: ignore
                    user_title=rule["title"],
                    user_message=rule["message"],
                    fix_action=rule.get("fix_action"),
                    technical_detail=f"exit_code={exit_code}\n{stderr}",
                    recovery_hint=rule.get("recovery_hint", ""),
                )

    # 3. 兜底解析：尝试提取 yt-dlp 的 ERROR/WARNING 行信息
    fallback_title = "解析或下载失败"
    fallback_msg = "系统遇到无法完全识别的错误，请查看错误原始日志。"

    # 匹配 HTTP 错误码
    http_match = re.search(r"HTTP Error (\d{3})", clean_msg, re.IGNORECASE)
    if http_match:
        code_str = http_match.group(1)
        code_int = int(code_str)
        fallback_title = f"网页请求失败 (HTTP {code_str})"
        desc = HTTP_STATUS_TRANSLATIONS.get(code_int, "未知 HTTP 状态码")
        fallback_msg = f"服务器返回了错误状态：{desc}。这可能是因为节点被风控或目标网站故障。"

    # 提取 [Extractor] 前缀的错误
    ext_match = re.search(r"ERROR:\s*\[([^\]]+)\]\s*(.*)", clean_msg, flags=re.IGNORECASE)
    if ext_match:
        extractor_raw = ext_match.group(1).strip()
        err_detail = ext_match.group(2).strip()

        extractor_name = EXTRACTOR_NAMES.get(extractor_raw.lower(), extractor_raw)

        # 组装更加智能的兜底文案
        if not http_match:
            fallback_title = f"{extractor_name} 解析失败"
            fallback_msg = f"提取组件在处理 {extractor_name} 的链接时遇到问题：\n{err_detail}"
            if len(fallback_msg) > 300:
                fallback_msg = fallback_msg[:297] + "..."

    return DiagnosedError(
        code=ErrorCode.GENERAL,
        severity="fatal",
        user_title=fallback_title,
        user_message=fallback_msg,
        fix_action=None,
        technical_detail=f"exit_code={exit_code}\n{stderr}",
        recovery_hint="",
    )


def probe_youtube_connectivity(timeout: float = 5.0) -> bool:
    """
    HEAD 请求 youtube.com 检测网络连通性（不经过 yt-dlp）。
    会自动读取应用内代理配置。
    """
    import urllib.request

    try:
        from ..core.config_manager import config_manager

        proxy_mode = str(config_manager.get("proxy_mode") or "off").lower().strip()
        proxy_url = str(config_manager.get("proxy_url", "") or "").strip()
    except Exception:
        proxy_mode = "off"
        proxy_url = ""

    try:
        req = urllib.request.Request(
            "https://www.youtube.com/",
            method="HEAD",
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
        )
        handlers: list = []
        if proxy_mode == "manual" and proxy_url:
            lower = proxy_url.lower()
            if not (
                lower.startswith("http://")
                or lower.startswith("https://")
                or lower.startswith("socks5://")
            ):
                proxy_url = "http://" + proxy_url
            handlers.append(urllib.request.ProxyHandler({"https": proxy_url, "http": proxy_url}))
        elif proxy_mode == "system":
            pass
        else:
            handlers.append(urllib.request.ProxyHandler({}))

        opener = urllib.request.build_opener(*handlers)
        resp = opener.open(req, timeout=timeout)
        return resp.status < 400
    except Exception:
        return False


def generate_issue_url(title: str, raw_error: str) -> str:
    """生成预填内容的 GitHub Issue 链接"""
    import urllib.parse

    max_err_len = 1500
    if len(raw_error) > max_err_len:
        raw_error = raw_error[:max_err_len] + "\n...[Truncated]"
    issue_title = urllib.parse.quote(f"[AutoReport] {title}")
    body = f"### 错误描述\n自动捕获到的错误：\n**{title}**\n\n### 错误日志\n```text\n{raw_error}\n```\n\n### 其他信息\n- FluentYTDL 版本: \n- 操作系统: \n"
    issue_body = urllib.parse.quote(body)
    return f"https://github.com/SakuraForgot/FluentYTDL/issues/new?title={issue_title}&body={issue_body}&labels=bug"
