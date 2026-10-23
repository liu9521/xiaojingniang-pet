# -*- coding: utf-8 -*-
"""驱动桌宠走一遍动作 + 台词，逐个截屏拼成验收图。"""
import ctypes
import time
import tkinter as tk
from pathlib import Path

ctypes.windll.shcore.SetProcessDpiAwareness(2)

from PIL import Image, ImageDraw, ImageFont, ImageGrab  # noqa: E402

import pet  # noqa: E402

OUT = Path(__file__).resolve().parent / "assets"
SHOTS = []

SEQ = [
    ("idle", "欢迎回来，主人～"),
    ("happy", "最喜欢主人了！"),
    ("shy", "呀…别、别这样啦。"),
    ("angry", "哼！不理你了。"),
    ("sleep", "晚安…Zzz"),
    ("eat", "小鱼干最好吃了！"),
    ("stretch", "伸个懒腰～"),
    ("spin", "转圈圈～"),
    ("look", "在找什么呢？"),
    ("work", "开始干活！"),
]


def grab(app, name):
    x = round(app.x)
    y = round(app.y)
    im = ImageGrab.grab(bbox=(x - 2, y - 2, x + app.win_w + 2, y + app.win_h + 2), all_screens=True)
    im.save(OUT / f"shot_{name}.png")
    SHOTS.append((name, im))
    print("shot", name, im.size, flush=True)


def main():
    root = tk.Tk()
    app = pet.PetApp(root)
    root.attributes("-topmost", True)

    def step(i=0):
        if i >= len(SEQ):
            root.after(200, finish)
            return
        key, text = SEQ[i]
        app.play(key, oneshot=False if key == "sleep" else True, speed=1.0)
        app.say(text, 6)
        root.after(750, lambda: (grab(app, key), root.after(300, lambda: step(i + 1))))

    def finish():
        cols = 5
        w, h = SHOTS[0][1].size
        sheet = Image.new("RGB", (cols * w, ((len(SHOTS) + cols - 1) // cols) * (h + 22)), (235, 238, 246))
        d = ImageDraw.Draw(sheet)
        font = ImageFont.truetype(r"C:\Windows\Fonts\msyhbd.ttc", 16)
        for k, (name, im) in enumerate(SHOTS):
            r, c = divmod(k, cols)
            sheet.paste(im, (c * w, r * (h + 22) + 22))
            d.text((c * w + 6, r * (h + 22) + 2), name, font=font, fill=(40, 46, 80))
        sheet.save(OUT / "actions.png")
        print("sheet ->", OUT / "actions.png")
        app.quit()

    root.after(1500, step)
    root.mainloop()


if __name__ == "__main__":
    main()
