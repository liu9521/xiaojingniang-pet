# -*- coding: utf-8 -*-
"""
从 dsh-whale-girl-pet (MIT) 的 webm 动画里抽取帧，裁切后逐帧编码为 WebP，
再拼成单个 .bin（附偏移索引），运行时按帧解码，内存占用低。

输出：assets/anim/<key>.bin + assets/anim/manifest.json
"""
from __future__ import annotations

import io
import json
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image

FF = r"D:\python\Lib\site-packages\imageio_ffmpeg\binaries\ffmpeg-win-x86_64-v7.1.exe"
SRC = Path(r"D:\deepseek work\_pkg\package\assets\thumb")
OUT = Path(__file__).resolve().parent / "assets" / "anim"
TMP = Path(r"D:\deepseek work\_pkg\_build")

CLIPS = {
    "idle": ("待机呼吸休闲", 12, (0.0, 5.0)),
    "look": ("东张西望", 20, None),
    "happy": ("点击回应 - 开心跃动", 20, None),
    "shy": ("点击回应 - 害羞惊讶", 20, None),
    "angry": ("点击回应 - 傲娇生气（侧身展示）", 20, None),
    "surprised": ("被吓一跳（炸毛）", 20, None),
    "sneeze": ("打喷嚏", 20, None),
    "yawn": ("哈欠连天", 20, None),
    "sleepy": ("迷糊犯困", 20, None),
    "sleep": ("睡觉第一段", 20, None),
    "wakeup": ("睡眼惺忪", 20, None),
    "eat": ("吃小鱼干", 20, None),
    "drink": ("喝奶茶", 20, None),
    "stretch": ("超大伸懒腰", 20, None),
    "bow": ("女仆屈膝礼仪", 20, None),
    "hum": ("悠闲哼歌", 20, None),
    "walk": ("原地漂浮踏步", 20, None),
    "spin": ("小幅度原地 360 度旋转展示", 20, None),
    "drag": ("被鼠标拖拽悬空反馈", 20, None),
    "work": ("认真工作", 20, None),
    "poke": ("原地敲击桌面互动", 20, None),
    "jump": ("原地跳跃抓碎头顶物品", 20, None),
    "tail": ("用鲸鱼尾巴拍打地面", 20, None),
}

W0, H0 = 360, 360
ALPHA_THR = 24
WIN_SEC = 3.4
WEBP_Q = 90


def decode_raw(path: Path) -> np.ndarray:
    raw = TMP / "clip.rgb"
    subprocess.run(
        [FF, "-y", "-hide_banner", "-loglevel", "error", "-c:v", "libvpx-vp9", "-i", str(path),
         "-f", "rawvideo", "-pix_fmt", "rgba", str(raw)],
        check=True,
    )
    data = np.fromfile(raw, dtype=np.uint8)
    n = data.size // (W0 * H0 * 4)
    raw.unlink()
    return data[: n * W0 * H0 * 4].reshape(n, H0, W0, 4)


def motion_curve(frames: np.ndarray) -> np.ndarray:
    small = frames[:, ::4, ::4, :].astype(np.float32)
    return np.abs(np.diff(small, axis=0)).mean(axis=(1, 2, 3))


def peak_window(frames, fps, seconds=WIN_SEC):
    cur = motion_curve(frames)
    n = max(2, int(seconds * fps / 3))
    sums = np.convolve(cur, np.ones(n), mode="valid")
    i = int(sums.argmax())
    start = max(0.0, i / fps - 0.35)
    return start, min(len(frames) / fps, start + seconds + 0.35)


def main():
    TMP.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("*.png"):
        old.unlink()

    box = [W0, H0, 0, 0]
    decoded: dict[str, np.ndarray] = {}
    for key, (name, fps, win) in CLIPS.items():
        frames = decode_raw(SRC / f"{name}.webm")
        decoded[key] = frames
        for f in frames[:: max(1, len(frames) // 12)]:
            ys, xs = np.where(f[:, :, 3] > ALPHA_THR)
            if len(xs):
                box = [min(box[0], int(xs.min())), min(box[1], int(ys.min())), max(box[2], int(xs.max())), max(box[3], int(ys.max()))]
    pad = 6
    x0 = max(0, box[0] - pad)
    y0 = max(0, box[1] - pad)
    x1 = min(W0, box[2] + pad)
    y1 = min(H0, box[3] + pad)
    cw, ch = int(x1 - x0), int(y1 - y0)
    print("crop", x0, y0, cw, ch)

    manifest = {"crop": [int(x0), int(y0), cw, ch], "clips": {}}

    for key, (name, fps, win) in CLIPS.items():
        frames = decoded[key]
        src_fps = 24.0
        s, e = win if win is not None else peak_window(frames, src_fps)
        i0 = int(round(s * src_fps))
        i1 = min(len(frames), int(round(e * src_fps)))
        n_out = max(2, int(round((i1 - i0) / src_fps * fps)))
        idx = [min(len(frames) - 1, i0 + int(round(k * src_fps / fps))) for k in range(n_out)]

        blob = bytearray()
        offsets = []
        for fi in idx:
            img = Image.fromarray(frames[fi], "RGBA").crop((x0, y0, x1, y1))
            buf = io.BytesIO()
            img.save(buf, "WEBP", quality=WEBP_Q, method=4, alpha_quality=100)
            data = buf.getvalue()
            offsets.append([len(blob), len(data)])
            blob += data
        (OUT / f"{key}.bin").write_bytes(bytes(blob))
        manifest["clips"][key] = {"fps": fps, "frames": n_out, "offsets": offsets}
        print(f"{key:10s} {s:5.2f}-{e:5.2f}s {n_out:3d}f {len(blob)/1024:6.0f}KB")

    (OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    total = sum(p.stat().st_size for p in OUT.glob("*.bin"))
    print(f"total {total/1024/1024:.1f} MB -> {OUT}")


if __name__ == "__main__":
    main()
