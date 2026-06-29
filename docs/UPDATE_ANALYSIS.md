# FluentYTDL 更新功能分析报告

## 一、架构概述

FluentYTDL 的自动更新系统采用 Telegram 风格的独立更新器架构，由以下组件构成：

### 核心组件

| 组件 | 文件 | 职责 |
|------|------|------|
| 更新协调器 | `src/fluentytdl/core/component_update_manager.py` | 版本检查、下载归档、启动 updater |
| 独立更新器 | `src/fluentytdl/core/updater.py` -> `updater.exe` | 等待主进程退出、替换文件、重启 |
| UI 卡片 | `src/fluentytdl/ui/components/app_update_card.py` | 设置页更新检查/下载界面 |
| 更新弹窗 | `src/fluentytdl/ui/components/update_dialog.py` | 更新日志+下载进度对话框 |
| 清单生成器 | `scripts/generate_manifest.py` | 构建时生成 `update-manifest.json` |
| 构建脚本 | `scripts/build.py` | 打包 `app-core.7z`（排除 bin/ 工具） |
| 启动清理 | `main.py` `_cleanup_update_residuals()` | 启动时清理残留并恢复失败更新 |

### 更新流程

```
用户点击"立即更新"
  -> ComponentUpdateManager.download_app_update(url, sha256)
  -> _DownloadWorker 下载 app-core.7z 到 %TEMP%（含 SHA256 校验，3 次重试）
  -> apply_app_core_update(archive_path)
  -> 启动 updater.exe --pid --archive --dest --exe
  -> 主程序 sys.exit(0)

updater.exe 运行:
  1. 等待主进程退出（30s 超时）
  2. 解压归档到 dest_dir/_update_tmp/ 临时目录（不触碰运行中文件）
  3. 验证解压结果（exe 存在、_internal 非空、VERSION 存在）
  4. 重命名 _internal/ -> _internal_old/，exe -> exe.old
  5. 从 _update_tmp/ 移动文件到 dest_dir/（原子替换）
  6. 若移动失败，完整回滚
  7. ShellExecuteW 启动新 FluentYTDL.exe
  8. 等待 2s，清理 _internal_old/ 和 .exe.old
  9. 删除归档文件，自删除 updater.exe
```

### 版本通道

| 前缀 | 通道 | 行为 |
|------|------|------|
| `v-` | stable | 支持 RAW 直链检查更新和自动下载安装 |
| `pre-` | locked | 不支持自动更新，提示去 GitHub 手动下载 |
| `beta-` | locked | 不支持自动更新，提示去 GitHub 手动下载 |

### 清单获取

使用 RAW 直链 `https://github.com/SakuraForgot/FluentYTDL/releases/latest/download/update-manifest.json`，
GitHub `releases/latest/download/` 自动 302 重定向到最新 release asset，**完全绕过 GitHub API 速率限制**。

失败时回退到本地缓存清单（7 天有效期，存储在 `update_manifest_cache.json`）。

---

## 二、问题报告与修复记录

### P0-1: updater.exe 自覆盖死锁（根因） - 已修复

**问题**: `app-core.7z` 归档内包含 `updater.exe`。updater（onefile 模式）解压归档时尝试覆写正在运行的 `updater.exe`，
导致 `py7zr.extractall()` 抛出 `PermissionError`，部分 `_internal/` 文件未被解压，应用损坏。

**修复**:
1. 从 `app-core.7z` 归档中排除 `updater.exe`（`build.py` `create_app_core_7z()` 和 `generate_manifest.py`）
2. updater.exe 的更新通过延迟替换机制（`updater.exe.new` -> `main.py` 启动时替换）

### P0-2: 解压失败回滚逻辑不完整 - 已修复

**问题**: 旧代码先重命名旧文件再解压，若解压部分成功则回滚条件不满足，应用不可恢复。

**修复**: 重构为先解压到临时目录 `_update_tmp/`，验证通过后再原子替换。解压失败不影响现有文件。

### P1-1: 解压后无完整性校验 - 已修复

**修复**: 新增 `_verify_extraction()` 函数，检查 exe 存在且大小 > 0、`_internal/` 非空、VERSION 文件存在。

### P1-2: 下载无重试 - 已修复

**修复**: `_DownloadWorker` 新增 3 次重试 + 指数退避（1s, 2s），超时从 300s 提升到 600s。

### P1-3: 清单获取依赖 GitHub API - 已修复

**修复**: `_ManifestWorker` 改用 RAW 直链 `releases/latest/download/update-manifest.json`，删除 API 调用和 token 逻辑，
新增本地缓存回退（7 天有效期）。

### P1-4: updater 自删除竞态 - 已修复

**修复**: `self_delete()` 延迟从 1s 增加到 2s，新增二次重试。

### P2-1: 版本比较逻辑冗余 - 已修复

**修复**: `_get_update_channel()` 简化为 `stable` / `locked`（beta/pre 统一）。删除 pre 通道 release 列举逻辑。
`_compare_app_version()` 删除 `is_prerelease` 过滤。

### P2-2: 更新失败无恢复 - 已修复

**修复**: `main.py` `_cleanup_update_residuals()` 新增恢复逻辑：
- `_internal_old/` 存在且 `_internal/` 不完整 -> 自动恢复
- `FluentYTDL.exe` 不存在但 `.exe.old` 存在 -> 自动恢复
- `_update_tmp/` 残留 -> 清理

### P2-4: 提权参数拼接有误 - 已修复

**修复**: `_elevate_self()` 重写参数构建逻辑，正确处理含空格路径。

---

## 三、涉及文件

| 文件 | 修改内容 |
|------|----------|
| `src/fluentytdl/core/updater.py` | 重构解压逻辑、完整性校验、修复自删除和提权 |
| `src/fluentytdl/core/component_update_manager.py` | RAW 直链、stable-only、下载重试、本地缓存 |
| `src/fluentytdl/ui/components/app_update_card.py` | locked 通道 UI 适配 |
| `src/fluentytdl/ui/components/update_dialog.py` | 简化跳过版本逻辑 |
| `scripts/generate_manifest.py` | 排除 updater.exe、内嵌 changelog |
| `scripts/build.py` | `create_app_core_7z()` 排除 updater.exe |
| `main.py` | 增强启动恢复逻辑 |
