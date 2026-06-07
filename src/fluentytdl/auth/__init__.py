"""
FluentYTDL 认证功能域

包含浏览器 Cookie 提取、验证状态管理、Cookie 生命周期管理等功能。
"""

from .auth_service import (
    ADMIN_REQUIRED_BROWSERS,
    BROWSER_SOURCES,
    AuthProfile,
    AuthService,
    AuthSourceType,
    AuthStatus,
    WebView2Account,
    auth_service,
    is_admin,
)
from .cookie_sentinel import CookieSentinel, cookie_sentinel

__all__ = [
    # 认证服务
    "AuthService",
    "auth_service",
    "AuthSourceType",
    "AuthStatus",
    "AuthProfile",
    "WebView2Account",
    "BROWSER_SOURCES",
    "ADMIN_REQUIRED_BROWSERS",
    "is_admin",
    # Cookie 哨兵
    "CookieSentinel",
    "cookie_sentinel",
]
