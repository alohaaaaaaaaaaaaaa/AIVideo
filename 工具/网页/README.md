# 网页原文与查阅动画

入口均从工作室根目录调用 `.venv/bin/python`，文件路径相对各配置文件解释。完整操作与参数见 `文档/09_网页抓取与网页动画.md`，可以播放的实际参考在 `参考库/网页取证/看网页参考.html`。

```bash
.venv/bin/python 工具/网页/capture_evidence.py 配置.json --output 新取证目录
.venv/bin/python 工具/网页/audit_capture.py 新取证目录/capture.json --output 坐标核验.json
.venv/bin/python 工具/网页/animate_evidence.py 制作配置.json --output 新版本镜头.mp4
.venv/bin/python 工具/网页/verify_pipeline.py --output 新失败模式测试目录
```

首次准备安装 `requirements.txt` 与 `python -m playwright install chromium`。抓取也可以使用 `--browser` 指向已安装 Chromium。测试只在本地使用无新闻含义的夹具和回环 HTTP，不依赖新闻网站。

可复用动作：`fullframe` 在原图全幅上按实音坐标划线；`capture_focus` 用 `capture.json` 的 DOM 坐标聚焦原段并划线；`page_scroll` 在真实连续页面像素中作短滚动并停住；`cursor_click` 在真实标题截图上制作查阅点击动作。上述编辑层不冒充网站原控件或历史屏幕录像。
