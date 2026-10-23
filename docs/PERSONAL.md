# 个人版使用与构建

## 连接与账号

每个人在自己的电脑上运行服务、登录自己的 QQ 并选择订阅群。`.env.example` 是空白模板，复制为 `.env` 后配置；真实 `.env`、数据库、群消息、API key 和 token 均不进仓库。

`/console` 保留原版管理功能，用于 QQ 登录、选群和模型设置；`/` 是新版作业与事项看板，`/calendar` 打开新版月历。网页中的连接设置显示本机实际连接信息。请使用自己服务生成的 token。

Android 个人版可手动输入电脑地址与 token，或通过 `noticehub-personal://connect?base=...&token=...` 链接连接。原版 `noticehub://` 链接属于原版客户端，不能混用。首次运行的个人版没有预设服务器。

iPhone：浏览器打开自己电脑的地址与 token；日历添加服务器生成的 `/calendar.ics?token=...` 订阅。日历订阅为只读并由系统定期更新，完成/收藏等操作在网页进行。没有 IPA 或官方 iOS 版本附在本发布中。

外出使用时，手机与电脑需要可互通的网络；使用 Tailscale 时，按需连接后查看即可。断开后无法刷新远端服务。电脑关机或休眠后，手机无法获取新内容。通知推送需要另行配置通道。

## 识别与确认

作业分类使用文本规则，覆盖作业、习题、课后练习、实验报告等表达；不保证任意措辞都能识别。标题与时间提取、跨群归并也存在误判可能，请核对原文。待确认的事项需用户确认是否为待办；时间冲突不会被静默移到另一天。疑似同一事件保留各自状态，由用户决定合并或分开。

## 构建 Windows 服务

在仓库根目录运行（需要 Python 3.12+）：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt pyinstaller
.\.venv\Scripts\python.exe -m PyInstaller --noconfirm packaging/personal_service.spec
```

输出为 `dist/qq-live-digest-personal.exe`。Release 中的服务包仅包含个人版服务、空白配置、启动脚本及说明；NapCat 需按上游接入指南单独安装。双击 `start-personal.cmd` 启动，保持窗口运行。首次部署检查配置后打开控制台连接 QQ。

## 验证范围

Python 测试涵盖识别、截止时间、归并、存储和 HTTP 路由；合成数据的浏览器检查覆盖手机/电脑长正文展开收起与日历。Android APK 经过编译与签名校验，未在所有机型或 iOS 实机上验证。识别与归并不是可靠的作业交付保证，请保留课程原始通知渠道。

## 更新已有部署

先备份自己的 `.env` 和 `data/`，停止旧服务，再更新程序文件。不要用本仓库的 `.env.example` 覆盖自己的 `.env`。Android 更新需要同一签名；自行编译使用自己的签名时，可能需要卸载原包并重新连接。

## 自动检查

本分支保留原版 unittest 工作流；个人版参数化回归测试请安装 `requirements-dev.txt` 后运行 `python -m pytest -q`。未安装 pytest 时，unittest 会跳过依赖它的个人版模块。完整测试在发布前于 Windows 本地运行。

浏览器回归检查：安装 Node.js 与 Playwright、浏览器后，在根目录执行 `node tools/ui_body_collapse_check.cjs`；可通过 `CHROME_PATH` 指定已有 Chromium 浏览器。检查使用虚构数据。
