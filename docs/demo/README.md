# 宣传视频与虚构演示数据

Release 附有 `qunwutai-xuanchuan.mp4`，约 45 秒，720×1280。截图里的课程群名与消息均为虚构。配乐由脚本合成；旁白由 Windows 系统语音生成。

重新制作：Node.js 安装 `playwright` 并执行 `npx playwright install chromium`；在本目录执行 `node capture.cjs`。也可通过 `CHROME_PATH` 指定已安装 Chromium/Edge。演示日期固定为 2026-10，不连接真实服务。

Windows 运行 `create-narration.ps1` 生成中文旁白（需系统安装中文语音）；Python 安装 `numpy pillow`，准备 PATH 中的 FFmpeg 或设置 `FFMPEG` 环境变量，执行 `python render_video.py`。字体默认使用 Windows 的微软雅黑。
