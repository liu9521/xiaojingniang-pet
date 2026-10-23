# -*- coding: utf-8 -*-
"""
小鲸鱼娘桌宠 · 安装程序
========================
把打包好的程序目录复制到 %LOCALAPPDATA%\\XiaoJingNiang，
创建桌面 / 开始菜单 / 开机启动快捷方式，并附带卸载脚本。

参数：
  （无）        交互安装
  --silent     静默安装，不弹窗、不自动启动（测试用）
  --uninstall  卸载
"""

from __future__ import annotations

import ctypes
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

APP_TITLE = "小鲸鱼娘 · DeepSeek 桌宠"
EXE_NAME = "小鲸鱼娘.exe"
TARGET = Path(os.environ.get("XJN_TARGET") or (Path(os.environ["LOCALAPPDATA"]) / "XiaoJingNiang"))
NO_LINKS = os.environ.get("XJN_NO_LINKS") == "1"   # 自测用：不写桌面/开始菜单
SRC = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent)) / "app"

MB_OK = 0x0
MB_OKCANCEL = 0x1
MB_ICONINFORMATION = 0x40
MB_ICONQUESTION = 0x20
MB_ICONERROR = 0x10


def msg(text: str, title: str = "小鲸鱼娘", flags: int = MB_OK | MB_ICONINFORMATION) -> int:
    return ctypes.windll.user32.MessageBoxW(None, text, title, flags)


def desktop_dir() -> Path:
    for p in (Path(os.environ.get("OneDrive", "")) / "Desktop", Path(os.environ["USERPROFILE"]) / "Desktop"):
        if p.exists():
            return p
    return Path(os.environ["USERPROFILE"]) / "Desktop"


def start_menu() -> Path:
    return Path(os.environ["APPDATA"]) / "Microsoft/Windows/Start Menu/Programs"


def ps(script: str):
    fd, path = tempfile.mkstemp(suffix=".ps1")
    os.close(fd)
    try:
        Path(path).write_text(script, encoding="utf-8-sig")
        subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", path],
            capture_output=True,
            creationflags=0x08000000,
        )
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


def make_link(lnk: Path, target: str, args: str, workdir: str, desc: str):
    lnk.parent.mkdir(parents=True, exist_ok=True)
    ps(
        f"""
$ws = New-Object -ComObject WScript.Shell
$s = $ws.CreateShortcut('{lnk}')
$s.TargetPath = '{target}'
$s.Arguments = '{args}'
$s.WorkingDirectory = '{workdir}'
$s.IconLocation = '{target},0'
$s.Description = '{desc}'
$s.Save()
"""
    )


def kill_running():
    subprocess.run(
        ["taskkill", "/f", "/im", EXE_NAME],
        capture_output=True,
        creationflags=0x08000000,
    )


def write_uninstaller(target: Path):
    """卸载脚本：结束进程 → 删快捷方式 → 延时删除安装目录。"""
    script = f"""$ErrorActionPreference = 'SilentlyContinue'
$dir = '{target}'
$exe = '{EXE_NAME}'
Get-Process $exe.Replace('.exe','') | Stop-Process -Force
Remove-Item (Join-Path $env:USERPROFILE 'Desktop\\小鲸鱼娘.lnk')
Remove-Item (Join-Path $env:OneDrive 'Desktop\\小鲸鱼娘.lnk')
Remove-Item (Join-Path $env:APPDATA 'Microsoft\\Windows\\Start Menu\\Programs\\小鲸鱼娘.lnk')
Remove-Item (Join-Path $env:APPDATA 'Microsoft\\Windows\\Start Menu\\Programs\\Startup\\小鲸鱼娘.lnk')
Start-Process -WindowStyle Hidden cmd -ArgumentList ('/c ping -n 3 127.0.0.1 >nul & rmdir /s /q "' + $dir + '"')
"""
    p = target / "卸载小鲸鱼娘.ps1"
    p.write_text(script, encoding="utf-8-sig")
    return p


README = """小鲸鱼娘 · DeepSeek 桌宠
==========================

怎么玩
  双击      打开本机 DeepSeek Harness（已在运行会切到前台）
  单击      摸摸头（开心 / 害羞 / 生气 / 敲桌子）
  拖拽      放到桌面任意位置，松手就停在那儿
  右键      打开 DeepSeek、喂小鱼干、喝奶茶、转圈、唱歌、工作、睡觉、
            置顶、开机自启、退出

卸载
  开始菜单 → 小鲸鱼娘 → 卸载小鲸鱼娘
  或运行本目录下的「卸载小鲸鱼娘.ps1」

数据
  存档在 %APPDATA%\\DeepSeekPet\\state.json，卸载不会删除。

素材
  角色动画来自开源项目 dsh-whale-girl-pet（MIT License）。
"""


def install(silent: bool = False) -> bool:
    exe_src = SRC / EXE_NAME
    if not exe_src.exists():
        msg(f"安装文件不完整：找不到\n{exe_src}", APP_TITLE, MB_OK | MB_ICONERROR)
        return False

    if not silent:
        ans = msg(
            f"把「小鲸鱼娘」安装到这台电脑吗？\n\n位置：{TARGET}\n\n"
            "安装后会创建桌面快捷方式，并随开机自动启动。",
            APP_TITLE,
            MB_OKCANCEL | MB_ICONQUESTION,
        )
        if ans != 1:  # IDOK
            return False

    kill_running()
    TARGET.mkdir(parents=True, exist_ok=True)
    # 覆盖式复制（保留用户存档在 %APPDATA%，不受影响）
    for item in SRC.iterdir():
        dst = TARGET / item.name
        if item.is_dir():
            shutil.copytree(item, dst, dirs_exist_ok=True)
        else:
            shutil.copy2(item, dst)

    exe = TARGET / EXE_NAME
    (TARGET / "使用说明.txt").write_text(README, encoding="utf-8-sig")
    uninst = write_uninstaller(TARGET)

    if NO_LINKS:
        return True
    make_link(desktop_dir() / "小鲸鱼娘.lnk", str(exe), "", str(TARGET), APP_TITLE)
    make_link(start_menu() / "小鲸鱼娘.lnk", str(exe), "", str(TARGET), APP_TITLE)
    make_link(
        start_menu() / "Startup" / "小鲸鱼娘.lnk", str(exe), "", str(TARGET), APP_TITLE
    )
    make_link(
        start_menu() / "卸载小鲸鱼娘.lnk",
        "powershell.exe",
        f'-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "{uninst}"',
        str(TARGET),
        "卸载小鲸鱼娘",
    )

    if not silent:
        subprocess.Popen([str(exe)], cwd=str(TARGET))
        msg(
            "安装完成！\n\n桌面上的「小鲸鱼娘」双击即可启动，\n"
            "她会自己待在屏幕角落，点她可以打开 DeepSeek。",
            APP_TITLE,
        )
    return True


def uninstall(silent: bool = False) -> bool:
    if not silent:
        if msg("确定要卸载「小鲸鱼娘」吗？", APP_TITLE, MB_OKCANCEL | MB_ICONQUESTION) != 1:
            return False
    kill_running()
    for p in (
        desktop_dir() / "小鲸鱼娘.lnk",
        start_menu() / "小鲸鱼娘.lnk",
        start_menu() / "Startup" / "小鲸鱼娘.lnk",
        start_menu() / "卸载小鲸鱼娘.lnk",
    ):
        try:
            p.unlink()
        except OSError:
            pass
    if TARGET.exists():
        subprocess.Popen(
            ["cmd", "/c", "ping -n 3 127.0.0.1 >nul & rmdir /s /q", str(TARGET)],
            creationflags=0x08000000,
        )
    if not silent:
        msg("已卸载。存档仍保留在 %APPDATA%\\DeepSeekPet。", APP_TITLE)
    return True


def main():
    args = [a.lower() for a in sys.argv[1:]]
    silent = "--silent" in args
    try:
        if "--uninstall" in args or "/uninstall" in args:
            uninstall(silent)
        else:
            install(silent)
    except Exception as exc:
        msg(f"安装失败：{exc}", APP_TITLE, MB_OK | MB_ICONERROR)
        raise


if __name__ == "__main__":
    main()
