# 第三方素材声明 / Third-Party Notices

## dsh-whale-girl-pet

- 来源：npm 包 [`dsh-whale-girl-pet`](https://www.npmjs.com/package/dsh-whale-girl-pet)（v0.3.10）
- 许可：MIT License
- 版权：Copyright (c) 2026 dsh-whale-girl-pet contributors

本项目使用的部分：

| 内容 | 用途 |
| --- | --- |
| `assets/thumb/*.webm`（角色动画） | 逐帧解码、裁切、重新编码为 `assets/anim/*.bin`（WebP 帧包） |
| 角色形象 | 桌宠视觉主体 |

处理方式说明：

- 原始 webm 为 360×360、24fps、VP9 + alpha 通道
- 用 ffmpeg（libvpx-vp9 解码器保留 alpha）导出 RGBA 帧
- 自动检测每段动画的有效动作区间，裁切到统一包围盒
- 逐帧编码为 WebP（质量 90），打包成 `<动作名>.bin` + 偏移索引 `manifest.json`
- 运行时按帧解码，带 LRU 缓存，不常驻全部帧

本项目未修改角色形象的绘制内容，仅做格式转换与桌面端运行时重写。

MIT 许可允许再分发与修改，但要求保留上述版权声明与许可声明 —— 本文件与
[LICENSE](LICENSE) 即为该要求的履行方式。若你二次分发本项目，请一并保留。

## Python / Pillow / PyInstaller

- Python（PSF License）、Pillow（MIT-CMU License）、PyInstaller（GPL with exception）
- 仅作为运行时/打包工具使用，未修改其源码

## 字体

气泡文字使用系统字体 `Microsoft YaHei UI`（Windows 自带），未随项目分发字体文件。
