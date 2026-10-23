# -*- coding: utf-8 -*-
"""
DeepSeek 桌宠 · 小鲸娘（蓝发女仆）
=====================================
· 透明置顶窗口，会呼吸、眨眼、东张西望、睡觉、哼歌、转圈
· 单击摸头（随机反应），双击打开 DeepSeek，右键有完整菜单
· 可拖拽、会掉到任务栏上、会自己在桌面上散步
· 饱食度 / 心情 / 亲密度存档，喂食、玩耍、睡觉都有对应动画

美术素材来自开源项目 dsh-girl-pet（MIT），动画为逐帧 WebP 打包。
"""

from __future__ import annotations

import ctypes
import io
import json
import mmap
import os
import random
import struct
import subprocess
import sys
import tempfile
import time
import webbrowser
from collections import OrderedDict
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

# ---------------------------------------------------------------- 路径 / 常量
APP_NAME = "DeepSeekPet"
APP_TITLE = "小鲸娘 · DeepSeek 桌宠"
FROZEN = bool(getattr(sys, "frozen", False))          # 是否由 PyInstaller 打包运行
if FROZEN:
    APP_DIR = Path(sys.executable).resolve().parent
    ASSET = Path(getattr(sys, "_MEIPASS", APP_DIR)) / "assets"
else:
    APP_DIR = Path(__file__).resolve().parent
    ASSET = APP_DIR / "assets"
ANIM = ASSET / "anim"
MANIFEST = ANIM / "manifest.json"
DATA_DIR = Path(os.environ.get("APPDATA", str(APP_DIR))) / APP_NAME
DATA_DIR.mkdir(parents=True, exist_ok=True)
STATE_FILE = DATA_DIR / "state.json"
ICON_FILE = ASSET / "pet.ico"                       # 仓库里的备份
ICON_RUNTIME = DATA_DIR / "pet.ico"                 # 快捷方式实际引用（路径不能带空格）

KEY = "#010203"
KEY_RGB = (1, 2, 3)
FONT_BOLD = r"C:\Windows\Fonts\msyhbd.ttc"

DSH_EXE = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "DeepSeek Harness" / "DeepSeek Harness.exe"
DSH_WEB = "http://127.0.0.1:56487"
DEEPSEEK_WEB = "https://chat.deepseek.com"


def _dsh_candidates() -> list[Path]:
    """本机 DeepSeek Harness 客户端可能的位置。"""
    out = [
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "DeepSeek Harness" / "DeepSeek Harness.exe",
        Path(os.environ.get("PROGRAMFILES", "")) / "DeepSeek Harness" / "DeepSeek Harness.exe",
        Path(os.environ.get("PROGRAMFILES(X86)", "")) / "DeepSeek Harness" / "DeepSeek Harness.exe",
    ]
    for base in (os.environ.get("LOCALAPPDATA", ""), os.environ.get("PROGRAMFILES", "")):
        if not base:
            continue
        try:
            out += list(Path(base).glob("Programs/*/DeepSeek Harness.exe"))
            out += list(Path(base).glob("*DeepSeek*/DeepSeek Harness.exe"))
        except Exception:
            pass
    seen, uniq = set(), []
    for p in out:
        if p and str(p) not in seen:
            seen.add(str(p))
            uniq.append(p)
    return uniq


DSH_CANDIDATES = _dsh_candidates()


def _dpi_scale() -> float:
    if sys.platform != "win32":
        return 1.0
    user32 = ctypes.windll.user32
    aware = False
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
        aware = True
    except Exception:
        pass
    if not aware:
        try:
            aware = bool(user32.SetProcessDpiAwarenessContext(-4))
        except Exception:
            pass
    if not aware:
        try:
            user32.SetProcessDPIAware()
        except Exception:
            pass
    try:
        dpi = user32.GetDpiForSystem()
    except Exception:
        dpi = 96
    return max(0.85, min(3.0, dpi / 96.0))


SCALE = _dpi_scale()


class RECT(ctypes.Structure):
    _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long), ("right", ctypes.c_long), ("bottom", ctypes.c_long)]


def work_area():
    r = RECT()
    try:
        if ctypes.windll.user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(r), 0):
            return r.left, r.top, r.right, r.bottom
    except Exception:
        pass
    return 0, 0, 1920, 1080


def clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


# ---------------------------------------------------------------- 动画仓库
class AnimBank:
    """把每个动作的 WebP 帧打包文件按需解码，带 LRU 缓存。"""

    def __init__(self, folder: Path):
        self.folder = folder
        man = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
        self.crop = man["crop"]
        self.clips = man["clips"]
        self.size = (self.crop[2], self.crop[3])
        self._maps: dict[str, tuple] = {}
        self._cache: OrderedDict = OrderedDict()
        self.cache_max = 50

    def blob(self, key: str):
        """内存映射帧包，避免把所有动作常驻内存。"""
        if key not in self._maps:
            fh = open(self.folder / f"{key}.bin", "rb")
            self._maps[key] = (fh, mmap.mmap(fh.fileno(), 0, access=mmap.ACCESS_READ))
        return self._maps[key][1]

    def frame(self, key: str, i: int) -> Image.Image:
        info = self.clips[key]
        i = max(0, min(info["frames"] - 1, int(i)))
        ck = (key, i)
        img = self._cache.get(ck)
        if img is not None:
            self._cache.move_to_end(ck)
            return img
        off, ln = info["offsets"][i]
        img = Image.open(io.BytesIO(self.blob(key)[off : off + ln])).convert("RGBA")
        self._cache[ck] = img
        if len(self._cache) > self.cache_max:
            self._cache.popitem(last=False)
        return img


# ---------------------------------------------------------------- 气泡
_bubble_cache: dict[tuple, Image.Image] = {}


def _wrap(text: str, font, max_w: float):
    import re

    tokens = re.findall(r"[A-Za-z0-9_\-\.\?!/:']+|[\u4e00-\u9fff]|\s+|.", text)
    lines, cur = [], ""
    for tok in tokens:
        if tok == "\n":
            lines.append(cur)
            cur = ""
            continue
        if font.getlength(cur + tok) <= max_w or not cur:
            cur += tok
        else:
            lines.append(cur.rstrip())
            cur = tok.lstrip()
    if cur:
        lines.append(cur.rstrip())
    return lines or [""]


def make_bubble(text: str, fs: float = 15.0, max_w: float = 318.0) -> Image.Image:
    """蓝白配色圆角气泡 + 小尾巴 + 阴影。"""
    key = (text, round(fs, 1), round(max_w, 1))
    if key in _bubble_cache:
        return _bubble_cache[key]

    k = 2.0
    font = ImageFont.truetype(FONT_BOLD, max(10, int(round(fs * k))))
    pad_x, pad_y = 13.0, 9.0
    lines = _wrap(text, font, max(10.0, max_w - pad_x * 2) * k)
    tw = max(font.getlength(ln) for ln in lines)
    line_h = fs * 1.55
    bw = tw / k + pad_x * 2
    bh = len(lines) * line_h + pad_y * 2
    tail = 9.0
    W, H = bw + 10, bh + tail + 12
    bx0, by0 = 5.0, 5.0

    mask = Image.new("L", (round(W * k), round(H * k)), 0)
    md = ImageDraw.Draw(mask)
    md.rounded_rectangle([bx0 * k, by0 * k, (bx0 + bw) * k, (by0 + bh) * k], radius=14 * k, fill=255)
    cx = (bx0 + bw / 2) * k
    md.polygon(
        [(cx - 8 * k, (by0 + bh - 2) * k), (cx + 8 * k, (by0 + bh - 2) * k), (cx, (by0 + bh + tail) * k)],
        fill=255,
    )

    shadow = Image.new("RGBA", mask.size, (0, 0, 0, 0))
    shadow.putalpha(mask.filter(ImageFilter.GaussianBlur(3 * k)).point(lambda v: int(v * 0.20)))
    shadow = ImageChops.offset(shadow, 0, max(1, round(2 * k)))

    grow = max(1, int(round(1.8 * k)))
    border = ImageChops.subtract(mask.filter(ImageFilter.MaxFilter(grow * 2 + 1)), mask)
    border = border.filter(ImageFilter.GaussianBlur(0.6 * k))

    out = Image.new("RGBA", mask.size, (0, 0, 0, 0))
    out.alpha_composite(shadow)
    fill = Image.new("RGBA", mask.size, (255, 255, 255, 250))
    fill.putalpha(ImageChops.multiply(fill.getchannel("A"), mask))
    out.alpha_composite(fill)
    bd = Image.new("RGBA", mask.size, (150, 176, 240, 255))
    bd.putalpha(ImageChops.multiply(bd.getchannel("A"), border.point(lambda v: min(255, v * 3))))
    out.alpha_composite(bd)

    d = ImageDraw.Draw(out)
    for i, ln in enumerate(lines):
        y = (by0 + pad_y + i * line_h) * k
        d.text((bx0 * k + (bw * k - font.getlength(ln)) / 2, y), ln, font=font, fill=(38, 48, 92, 255))

    out = out.resize((round(W), round(H)), Image.LANCZOS)
    _bubble_cache[key] = out
    if len(_bubble_cache) > 40:
        _bubble_cache.clear()
    return out


# ---------------------------------------------------------------- 台词
LINES = {
    "hello": ["欢迎回来，主人～", "我一直在这里等您哦。", "今天也要好好加油！"],
    "idle": [
        "要开始工作了吗？",
        "命令已收到，随时可以出发。",
        "DeepSeek 已经准备好了。",
        "我在这里陪着您。",
        "要不要摸摸头？",
        "偷偷告诉您，我也在学写代码。",
        "CPU 在转，我的尾巴也在摇。",
        "双击我可以打开 DeepSeek 哦。",
        "记得喝水呀。",
        "写代码累了就看看我。",
    ],
    "happy": ["嘿嘿～", "最喜欢主人了！", "再摸一下嘛。", "开心！"],
    "shy": ["呀…别、别这样啦。", "脸有点热…", "太、太近了啦！"],
    "angry": ["哼！不理你了。", "人家在忙呢！", "再这样就生气了哦。"],
    "eat": ["小鱼干最好吃了！", "谢谢款待～", "还想再来一条…"],
    "drink": ["奶茶是续命水。", "咕嘟咕嘟…", "三分糖，谢谢。"],
    "sleep": ["晚安…Zzz", "我先眯一会儿。", "梦里也要工作吗…"],
    "wake": ["唔…我睡着了吗？", "早上好…", "睡饱了！"],
    "stretch": ["伸个懒腰～", "肩膀好酸。"],
    "work": ["开始干活！", "让我看看今天的任务。", "专注模式，启动。"],
    "drag": ["哇——放我下来！", "要掉下去了！"],
    "land": ["安全着陆。", "呼…吓我一跳。"],
    "night": ["这么晚还没睡？", "我先打个哈欠…", "夜深了，注意休息。"],
}
GREETINGS = ["摸摸头～", "嘿嘿，好舒服。", "主人今天心情好吗？"]


def pick(kind: str) -> str:
    return random.choice(LINES.get(kind) or LINES["idle"])


# ---------------------------------------------------------------- 存档
DEFAULT_STATE = {
    "hunger": 80.0,
    "mood": 86.0,
    "bond": 0.0,
    "x": None,
    "y": None,
    "autostart": True,
    "first_seen": None,
    "total_seconds": 0.0,
    "pets": 0,
    "feeds": 0,
    "plays": 0,
}


def load_state() -> dict:
    st = dict(DEFAULT_STATE)
    try:
        if STATE_FILE.exists():
            st.update(json.loads(STATE_FILE.read_text(encoding="utf-8")))
    except Exception:
        pass
    if not st.get("first_seen"):
        st["first_seen"] = time.time()
    return st


def save_state(st: dict):
    try:
        STATE_FILE.write_text(json.dumps(st, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


# ---------------------------------------------------------------- 快捷方式
def ps(script: str) -> str:
    fd, path = tempfile.mkstemp(suffix=".ps1")
    os.close(fd)
    try:
        Path(path).write_text(script, encoding="utf-8-sig")
        r = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", path],
            capture_output=True,
            text=True,
            creationflags=0x08000000,
        )
        return (r.stdout or "") + (r.stderr or "")
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


def pythonw() -> str:
    exe = Path(sys.executable)
    w = exe.with_name("pythonw.exe")
    return str(w if w.exists() else exe)


def launcher() -> tuple[str, str, str]:
    """快捷方式用的 (目标, 参数, 工作目录)。打包后直接指向 exe 自身。"""
    if FROZEN:
        exe = str(Path(sys.executable).resolve())
        return exe, "", str(Path(exe).parent)
    return pythonw(), f'"{APP_DIR / "pet.py"}"', str(APP_DIR)


def icon_ref() -> str:
    """快捷方式图标：打包后直接用 exe 内嵌图标，避免外部路径问题。"""
    if FROZEN:
        return f"{Path(sys.executable).resolve()},0"
    return str(ICON_RUNTIME)


def create_shortcut(lnk: Path, target: str, args: str, workdir: str, icon: str, desc: str):
    lnk.parent.mkdir(parents=True, exist_ok=True)
    ps(
        f"""
$ws = New-Object -ComObject WScript.Shell
$s = $ws.CreateShortcut('{lnk}')
$s.TargetPath = '{target}'
$s.Arguments = '{args}'
$s.WorkingDirectory = '{workdir}'
$s.IconLocation = '{icon}'
$s.Description = '{desc}'
$s.Save()
"""
    )


def startup_lnk() -> Path:
    return Path(os.environ["APPDATA"]) / "Microsoft/Windows/Start Menu/Programs/Startup/DeepSeekPet.lnk"


def desktop_lnk() -> Path:
    for p in (Path(os.environ.get("OneDrive", "")) / "Desktop", Path(os.environ["USERPROFILE"]) / "Desktop"):
        if p.exists():
            return p / "小鲸鱼娘.lnk"
    return Path(os.environ["USERPROFILE"]) / "Desktop" / "小鲸鱼娘.lnk"


def set_autostart(enabled: bool):
    lnk = startup_lnk()
    if enabled:
        target, args, workdir = launcher()
        create_shortcut(lnk, target, args, workdir, icon_ref(), "小鲸鱼娘")
    elif lnk.exists():
        try:
            lnk.unlink()
        except OSError:
            pass


def make_icon(bank: AnimBank):
    img = bank.frame("happy", 37).copy()
    bbox = img.getchannel("A").point(lambda v: 255 if v > 24 else 0).getbbox()
    if bbox:
        img = img.crop(bbox)
    size = 256
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ratio = min(size * 0.94 / img.width, size * 0.94 / img.height)
    img = img.resize((max(1, round(img.width * ratio)), max(1, round(img.height * ratio))), Image.LANCZOS)
    canvas.alpha_composite(img, ((size - img.width) // 2, (size - img.height) // 2))
    try:
        write_ico(canvas, ICON_FILE)
    except Exception:
        pass  # 打包运行时资源目录只读，写不进去也无所谓
    write_ico(canvas, ICON_RUNTIME)
    print("icon ->", ICON_RUNTIME)


def write_ico(img: Image.Image, path: Path, sizes=(16, 24, 32, 48, 64, 128, 256)):
    """手写 ICO：小尺寸用 32 位 BMP(DIB) 条目，只有 256 用 PNG。

    Pillow 自带的 ICO 写入会把所有尺寸都存成 PNG，资源管理器只认 256 的 PNG，
    其余会显示成空白图标，所以这里自己拼。
    """
    entries = []
    for s in sizes:
        im = img.resize((s, s), Image.LANCZOS)
        if s >= 256:
            buf = io.BytesIO()
            im.save(buf, "PNG", optimize=True)
            data = buf.getvalue()
            entries.append((0, 0, data))  # 0 表示 256
            continue
        px = im.load()
        rows = []
        for y in range(s - 1, -1, -1):
            row = bytearray()
            for x in range(s):
                r, g, b, a = px[x, y]
                row += bytes((b, g, r, a))
            rows.append(bytes(row))
        xor = b"".join(rows)
        mask_stride = ((s + 31) // 32) * 4
        mask = b"\x00" * (mask_stride * s)
        header = struct.pack("<IiiHHIIiiII", 40, s, s * 2, 1, 32, 0, len(xor) + len(mask), 0, 0, 0, 0)
        entries.append((s, s, header + xor + mask))

    offset = 6 + 16 * len(entries)
    directory = bytearray()
    blobs = bytearray()
    for w, h, data in entries:
        directory += struct.pack("<BBBBHHII", w % 256, h % 256, 0, 0, 1, 32, len(data), offset)
        blobs += data
        offset += len(data)
    path.write_bytes(struct.pack("<HHH", 0, 1, len(entries)) + bytes(directory) + bytes(blobs))


# ---------------------------------------------------------------- 主程序
class PetApp:
    def __init__(self, root):
        import tkinter as tk

        self.tk = tk
        self.root = root
        self.bank = AnimBank(ANIM)
        self.sw, self.sh = self.bank.size
        self.state_data = load_state()

        # 整体缩放（1.0 = 原始素材大小）
        self.zoom = 0.72
        self.dw = round(self.sw * self.zoom)
        self.dh = round(self.sh * self.zoom)
        self.win_w = max(self.dw + 20, 300)
        self.bubble_h = 104
        self.win_h = self.dh + self.bubble_h + 14
        self.sprite_x = (self.win_w - self.dw) // 2
        self.sprite_y = self.win_h - self.dh - 8
        self.head_top_px = round(self._detect_head_top() * self.zoom)

        root.overrideredirect(True)
        root.attributes("-topmost", True)
        root.configure(bg=KEY)
        try:
            root.wm_attributes("-transparentcolor", KEY)
            root.wm_attributes("-toolwindow", True)
        except Exception:
            pass
        root.title(APP_TITLE)

        self.left, self.top, self.right, self.bottom = work_area()
        self.ground = self.bottom - self.win_h
        sx, sy = self.state_data.get("x"), self.state_data.get("y")
        self.x = float(clamp(sx, self.left, self.right - self.win_w) if sx is not None else self.right - self.win_w - 60)
        self.y = float(clamp(sy, self.top, self.ground) if sy is not None else self.ground)

        self.canvas = tk.Canvas(root, width=self.win_w, height=self.win_h, bg=KEY, highlightthickness=0, bd=0)
        self.canvas.pack()
        self.item = self.canvas.create_image(0, 0, anchor="nw")
        self.bubble_item = self.canvas.create_image(0, 6, anchor="nw", state="hidden")
        self._photo = None
        self._bubble_photo = None

        self.now = time.perf_counter()
        self.last = self.now
        self.clip = "idle"
        self.frame_i = 0.0
        self.fps = 12
        self.oneshot = False
        self.next_idle = self.now + random.uniform(6, 12)
        self.next_talk = self.now + random.uniform(15, 30)
        self.bubble_until = 0.0
        self.vy = 0.0
        self.dragging = False
        self.drag_moved = False
        self.facing = -1
        self.walking_until = 0.0
        self.state_data.setdefault("pets", 0)
        self.last_save = self.now
        self.autostart = bool(self.state_data.get("autostart", True))

        self._bind()
        self._place()
        self.say(pick("hello") if self.state_data["pets"] else "初次见面，我是小鲸娘～双击我打开 DeepSeek！", 5.5)
        self.draw()
        self.root.after(0, self.tick)
        self.root.after(1200, self.keep_top)

    def _detect_head_top(self) -> int:
        """素材帧顶部留有放特效的空白，用待机动画估一下角色头顶的位置。"""
        try:
            info = self.bank.clips["idle"]
            tops = []
            for i in range(0, info["frames"], 4):
                b = self.bank.frame("idle", i).getchannel("A").point(lambda v: 255 if v > 30 else 0).getbbox()
                if b:
                    tops.append(b[1])
            return min(tops) if tops else 0
        except Exception:
            return 0

    def hwnd(self) -> int:
        frame = self.root.frame()
        return int(frame, 16) if str(frame).startswith("0x") else int(frame)

    def keep_top(self):
        """别的置顶窗口（如 Harness）抢到前面时，把自己再顶上去。"""
        try:
            ctypes.windll.user32.SetWindowPos(self.hwnd(), -1, 0, 0, 0, 0, 0x0003)
        except Exception:
            pass
        self.root.after(2500, self.keep_top)

    # -- 窗口
    def _place(self):
        self.root.geometry(f"{self.win_w}x{self.win_h}+{round(self.x)}+{round(self.y)}")

    def _bind(self):
        c = self.canvas
        c.bind("<ButtonPress-1>", self.on_press)
        c.bind("<B1-Motion>", self.on_drag)
        c.bind("<ButtonRelease-1>", self.on_release)
        c.bind("<Double-Button-1>", self.on_double)
        c.bind("<Button-3>", self.on_menu)
        c.bind("<Enter>", lambda e: c.configure(cursor="hand2"))
        c.bind("<Leave>", lambda e: c.configure(cursor=""))

    # -- 动作
    def play(self, key: str, oneshot: bool = True, speed: float = 1.0, after: str = "idle"):
        if key not in self.bank.clips:
            key = "idle"
        self.clip = key
        self.fps = self.bank.clips[key]["fps"] * speed
        self.frame_i = 0.0
        self.oneshot = oneshot
        self.after_clip = after

    def say(self, text: str, duration: float = 4.0):
        img = make_bubble(text, fs=14.0, max_w=self.win_w - 18)
        self._bubble_photo = self._to_tk(img)
        # 气泡贴着头顶（head_top 为素材里角色头顶相对帧顶的距离）
        head_y = self.sprite_y + self.head_top_px
        self.canvas.coords(
            self.bubble_item, (self.win_w - img.width) // 2, max(2, head_y - img.height - 2)
        )
        self.canvas.itemconfigure(self.bubble_item, image=self._bubble_photo, state="normal")
        self.bubble_until = self.now + duration

    def hide_bubble(self):
        self.canvas.itemconfigure(self.bubble_item, state="hidden")

    def _to_tk(self, img):
        from PIL import ImageTk

        return ImageTk.PhotoImage(img)

    # -- 鼠标
    def on_press(self, e):
        self.dragging = True
        self.drag_moved = False
        self.press = (e.x_root, e.y_root)
        self.win_xy = (self.x, self.y)

    def on_drag(self, e):
        if not self.dragging:
            return
        dx = e.x_root - self.press[0]
        dy = e.y_root - self.press[1]
        if abs(dx) > 4 or abs(dy) > 4:
            self.drag_moved = True
        if self.drag_moved:
            if self.clip != "drag":
                self.play("drag", oneshot=False, speed=1.1)
            # 可以拖到桌面任意位置，但别让她整只跑出屏幕
            self.x = clamp(self.win_xy[0] + dx, self.left, self.right - self.win_w)
            self.y = clamp(self.win_xy[1] + dy, self.top, self.bottom - self.win_h)
            self._place()

    def on_release(self, e):
        if not self.dragging:
            return
        self.dragging = False
        if self.drag_moved:
            # 松手就停在这里，不再掉下去
            self.play("bow", speed=1.15)
            if random.random() < 0.35:
                self.say(random.choice(["放在这里也可以～", "这个位置不错！", "就待在这儿啦。"]), 2.6)
        else:
            self._click_job = self.root.after(240, self.pet_head)

    def on_double(self, e):
        job = getattr(self, "_click_job", None)
        if job:
            try:
                self.root.after_cancel(job)
            except Exception:
                pass
            self._click_job = None
        self.drag_moved = True
        self.open_deepseek()
        self.play("happy", speed=1.25)
        self.say(random.choice(LINES["happy"]), 2.6)

    def pet_head(self):
        mood = self.state_data["mood"]
        roll = random.random()
        if mood < 30:
            self.play("angry", speed=1.2)
            kind = "angry"
        elif roll < 0.5:
            self.play("happy", speed=1.25)
            kind = "happy"
        elif roll < 0.8:
            self.play("shy", speed=1.2)
            kind = "shy"
        else:
            self.play("poke", speed=1.2)
            kind = "happy"
        self.say(pick(kind), 3.0)
        self.state_data["pets"] += 1
        self.state_data["mood"] = clamp(self.state_data["mood"] + 1.6, 0, 100)
        self.state_data["bond"] = self.state_data.get("bond", 0) + 1.2

    # -- 菜单
    def on_menu(self, e):
        tk = self.tk
        m = tk.Menu(self.root, tearoff=0, font=("Microsoft YaHei UI", 9))
        m.add_command(label="打开 DeepSeek Harness（本地客户端）", command=self.open_deepseek)
        m.add_command(label="打开 DeepSeek 网页版", command=lambda: webbrowser.open(DEEPSEEK_WEB))
        m.add_command(label="打开 Harness 界面", command=lambda: webbrowser.open(DSH_WEB))
        m.add_separator()
        m.add_command(
            label=f"饱食 {int(self.state_data['hunger'])}%   心情 {int(self.state_data['mood'])}%   亲密度 Lv.{self.level()}",
            state="disabled",
        )
        m.add_command(label=f"已陪伴 {self.playtime()}   被摸 {self.state_data['pets']} 次", state="disabled")
        m.add_separator()
        m.add_command(label="摸摸头", command=self.pet_head)
        m.add_command(label="喂小鱼干", command=self.feed)
        m.add_command(label="请她喝奶茶", command=self.drink)
        m.add_command(label="陪她玩（转圈）", command=self.spin)
        m.add_command(label="让她唱歌", command=self.sing)
        m.add_command(label="开始工作", command=self.work)
        m.add_command(label="睡一会儿 / 叫醒", command=self.toggle_sleep)
        m.add_command(label="伸懒腰", command=self.stretch)
        m.add_command(label="随便说句话", command=lambda: self.say(pick("idle"), 3.5))
        m.add_separator()
        self.var_top = tk.BooleanVar(value=True)
        m.add_checkbutton(label="窗口置顶", variable=self.var_top,
                          command=lambda: self.root.attributes("-topmost", self.var_top.get()))
        self.var_start = tk.BooleanVar(value=self.autostart)
        m.add_checkbutton(label="开机自动启动", variable=self.var_start, command=self.toggle_autostart)
        m.add_separator()
        m.add_command(label="退出小鲸娘", command=self.quit)
        try:
            m.tk_popup(e.x_root, e.y_root)
        finally:
            m.grab_release()

    def level(self):
        return clamp(1 + int((self.state_data.get("bond", 0) / 12) ** 0.75 * 2), 1, 99)

    def playtime(self):
        total = self.state_data.get("total_seconds", 0)
        h, mnt = divmod(int(total // 60), 60)
        return f"{h} 小时 {mnt} 分" if h else f"{mnt} 分钟"

    def toggle_autostart(self):
        self.autostart = bool(self.var_start.get())
        set_autostart(self.autostart)
        self.state_data["autostart"] = self.autostart
        save_state(self.state_data)

    def quit(self):
        self.save()
        self.root.destroy()

    # -- 各种互动
    def feed(self):
        self.play("eat", speed=1.1)
        self.say(pick("eat"), 3.2)
        self.state_data["hunger"] = clamp(self.state_data["hunger"] + 16, 0, 100)
        self.state_data["mood"] = clamp(self.state_data["mood"] + 4, 0, 100)
        self.state_data["feeds"] = self.state_data.get("feeds", 0) + 1

    def drink(self):
        self.play("drink", speed=1.1)
        self.say(pick("drink"), 3.2)
        self.state_data["mood"] = clamp(self.state_data["mood"] + 5, 0, 100)

    def spin(self):
        self.play("spin", speed=1.0)
        self.say("转圈圈～", 2.4)
        self.state_data["mood"] = clamp(self.state_data["mood"] + 8, 0, 100)
        self.state_data["plays"] = self.state_data.get("plays", 0) + 1

    def sing(self):
        self.play("hum", speed=1.0)
        self.say("♪ 啦啦啦～", 3.0)

    def work(self):
        self.play("work", speed=1.0)
        self.say(pick("work"), 3.0)

    def stretch(self):
        self.play("stretch", speed=1.0)
        self.say(pick("stretch"), 2.6)

    def toggle_sleep(self):
        if self.clip in ("sleep", "sleepy"):
            self.wake()
        else:
            self.play("sleep", oneshot=False, speed=1.0)
            self.say(pick("sleep"), 3.0)

    def wake(self):
        self.play("wakeup", speed=1.15)
        self.say(pick("wake"), 3.0)

    def open_deepseek(self):
        """唤起本机已安装的 DeepSeek Harness；没在运行就启动它。"""
        if self.focus_deepseek():
            return
        for exe in DSH_CANDIDATES:
            if exe.exists():
                try:
                    os.startfile(str(exe))
                    return
                except Exception:
                    try:
                        subprocess.Popen([str(exe)], cwd=str(exe.parent))
                        return
                    except Exception:
                        continue
        webbrowser.open(DEEPSEEK_WEB)

    def focus_deepseek(self) -> bool:
        """把已运行的 Harness 主窗口激活到前台。"""
        if sys.platform != "win32":
            return False
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        hits = []

        def proc_name(hwnd) -> str:
            pid = ctypes.c_ulong(0)
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            h = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
            if not h:
                return ""
            try:
                buf = ctypes.create_unicode_buffer(1024)
                size = ctypes.c_ulong(1024)
                if kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
                    return Path(buf.value).name
            finally:
                kernel32.CloseHandle(h)
            return ""

        @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
        def cb(hwnd, _):
            try:
                if not user32.IsWindowVisible(hwnd):
                    return True
                n = user32.GetWindowTextLengthW(hwnd)
                if n <= 0:
                    return True
                buf = ctypes.create_unicode_buffer(n + 1)
                user32.GetWindowTextW(hwnd, buf, n + 1)
                title = buf.value
                if "deepseek" not in title.lower() or "桌宠" in title:
                    return True
                if proc_name(hwnd).lower() != "deepseek harness.exe":
                    return True
                hits.append((n, hwnd))
            except Exception:
                pass
            return True

        user32.EnumWindows(cb, 0)
        if not hits:
            return False
        hits.sort(reverse=True)
        hwnd = hits[0][1]
        try:
            user32.ShowWindow(hwnd, 9)  # SW_RESTORE
            user32.SetForegroundWindow(hwnd)
            user32.BringWindowToTop(hwnd)
        except Exception:
            pass
        return True

    # -- 主循环
    def tick(self):
        try:
            self.now = time.perf_counter()
            dt = min(0.1, self.now - self.last)
            self.last = self.now
            self.update(dt)
            self.draw()
        except Exception as exc:
            print("tick error:", repr(exc), file=sys.stderr)
        self.root.after(33, self.tick)

    def update(self, dt):
        t = self.now

        # 任务栏/分辨率变化时，只把自己挪回可见范围（不再强制贴地）
        if t - getattr(self, "_wa_check", 0) > 2.0:
            self._wa_check = t
            l, tp, r, b = work_area()
            if (l, tp, r, b) != (self.left, self.top, self.right, self.bottom):
                self.left, self.top, self.right, self.bottom = l, tp, r, b
                self.ground = self.bottom - self.win_h
                self.x = clamp(self.x, self.left, max(self.left, self.right - self.win_w))
                self.y = clamp(self.y, self.top, max(self.top, self.bottom - self.win_h))
                self._place()

        # 走位（只在地面附近溜达，悬空时原地待着）
        if self.clip == "walk" and not self.dragging:
            if self.is_grounded():
                self.x += self.facing * 42.0 * dt
                if self.x < self.left - 10 or self.x > self.right - self.win_w + 10:
                    self.facing *= -1
                    self.x = clamp(self.x, self.left - 10, self.right - self.win_w + 10)
                self._place()
            else:
                self.play("idle", oneshot=False)

        # 逐帧播放
        self.frame_i += dt * self.fps
        frames = self.bank.clips[self.clip]["frames"]
        if self.frame_i >= frames:
            if self.oneshot:
                self.play(self.after_clip, oneshot=False)
            else:
                self.frame_i = 0.0

        if self.bubble_until and t > self.bubble_until:
            self.hide_bubble()
            self.bubble_until = 0.0

        # 自发行为
        if self.clip == "idle" and not self.dragging:
            if t > self.next_talk:
                self.say(pick("night" if self.is_night() else "idle"), 4.0)
                self.next_talk = t + random.uniform(35, 75)
            if t > self.next_idle:
                self.idle_action()
                self.next_idle = t + random.uniform(14, 32)

        # 数值
        self.state_data["hunger"] = clamp(self.state_data["hunger"] - dt * (100 / (5 * 3600)), 0, 100)
        self.state_data["mood"] = clamp(self.state_data["mood"] - dt * (100 / (8 * 3600)), 0, 100)
        self.state_data["total_seconds"] = self.state_data.get("total_seconds", 0) + dt
        if t - self.last_save > 30:
            self.save()
            self.last_save = t

    def save(self):
        self.state_data["x"] = round(self.x)
        self.state_data["y"] = round(self.y)
        save_state(self.state_data)

    def idle_action(self):
        low = self.state_data["hunger"] < 25
        if low and random.random() < 0.5:
            self.say("肚子饿了…有小鱼干吗？", 4.0)
            return
        r = random.random()
        if r < 0.18 and self.is_grounded():
            self.play("walk", oneshot=False, speed=1.0)
            self.walking_until = self.now + random.uniform(3.5, 6.5)
            self.facing = random.choice((-1, 1))
            self.root.after(int(random.uniform(3500, 6500) * 1000), self.stop_walk)
        elif r < 0.36:
            self.play("look", speed=1.0)
        elif r < 0.5:
            self.play("stretch" if random.random() < 0.5 else "yawn", speed=1.0)
        elif r < 0.62:
            self.play("tail", speed=1.0)
        elif r < 0.74:
            self.play("hum", speed=1.0)
        elif r < 0.84:
            self.play("sneeze", speed=1.1)
        elif r < 0.94:
            self.play("sleepy", speed=1.0)
        else:
            self.play("spin", speed=1.0)

    def stop_walk(self):
        if self.clip == "walk":
            self.play("idle", oneshot=False)
            self.next_idle = self.now + random.uniform(12, 25)

    def is_grounded(self) -> bool:
        return self.y >= self.ground - 6

    def is_night(self):
        hh = time.localtime().tm_hour
        return hh >= 23 or hh < 6

    def draw(self):
        frame = Image.new("RGB", (self.win_w, self.win_h), KEY_RGB)
        img = self.bank.frame(self.clip, int(self.frame_i))
        if (img.width, img.height) != (self.dw, self.dh):
            img = img.resize((self.dw, self.dh), Image.BILINEAR)
        frame.paste(img, (self.sprite_x, self.sprite_y), img)
        self._photo = self._to_tk(frame)
        self.canvas.itemconfigure(self.item, image=self._photo)


# ---------------------------------------------------------------- 入口
def single_instance_guard() -> bool:
    if sys.platform != "win32":
        return True
    kernel32 = ctypes.windll.kernel32
    handle = kernel32.CreateMutexW(None, False, "Global\\DeepSeekPetXiaoJing")
    if not handle:
        return True
    return kernel32.GetLastError() != 183


def install_shortcuts():
    """桌面 + 开机启动快捷方式。"""
    if not ICON_RUNTIME.exists():
        make_icon(AnimBank(ANIM))
    target, args, workdir = launcher()
    create_shortcut(desktop_lnk(), target, args, workdir, icon_ref(), "小鲸鱼娘 · DeepSeek 桌宠")
    set_autostart(True)
    print("桌面快捷方式:", desktop_lnk())
    print("开机启动:", startup_lnk())


def uninstall_shortcuts():
    for p in (desktop_lnk(), startup_lnk()):
        try:
            if p.exists():
                p.unlink()
                print("removed", p)
        except OSError:
            pass


def main():
    import tkinter as tk

    if FROZEN and sys.stdout is None:  # 打包成无控制台程序时，保证 print 不报错
        sys.stdout = open(os.devnull, "w", encoding="utf-8")
        sys.stderr = sys.stdout

    args = sys.argv[1:]
    bank = AnimBank(ANIM)
    if "--make-icon" in args:
        make_icon(bank)
        return
    if not ICON_FILE.exists() or not ICON_RUNTIME.exists():
        try:
            make_icon(bank)
        except Exception as exc:
            print("icon failed", exc)
    if "--install" in args:
        install_shortcuts()
        return
    if "--uninstall" in args:
        uninstall_shortcuts()
        return
    if not single_instance_guard():
        return
    try:
        root = tk.Tk()
        PetApp(root)
        root.mainloop()
    except Exception:
        import traceback
        (DATA_DIR / "error.log").write_text(traceback.format_exc(), encoding="utf-8")


if __name__ == "__main__":
    main()
