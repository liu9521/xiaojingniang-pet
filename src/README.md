# 小鲸娘 · DeepSeek 桌宠

一只住在 Windows 桌面上的蓝发鲸鱼女仆。透明无边框、始终置顶，会呼吸、眨眼、东张西望、
打哈欠、睡觉、哼歌、转圈、敲键盘；点她会摸头，双击直接打开 DeepSeek。

![桌面效果](assets/preview.png)

![动作一览](assets/actions.png)

## 怎么玩

| 操作 | 效果 |
| --- | --- |
| **双击** | 唤起本机的 DeepSeek Harness 客户端：已运行就直接切到前台（最小化也会还原），没运行就启动它；找不到客户端时才回退到网页版 |
| **单击** | 摸摸头：随机「开心 / 害羞 / 生气 / 敲桌子」反应 + 台词 |
| **拖拽** | 拎到桌面任意位置，松手就停在原地（不会自动掉下去），落地还会行个女仆礼 |
| **右键** | 菜单：打开 DeepSeek / 网页版 / Harness 界面、喂小鱼干、喝奶茶、转圈、唱歌、工作、睡觉、伸懒腰、状态、置顶、开机自启、退出 |

她还会自己找乐子：每 15～35 秒随机做个小动作（东张西望、伸懒腰、甩尾巴、哼歌、打喷嚏、
犯困、散步），偶尔自言自语。饿肚子时表情会变。

## 动作 / 表情

23 组逐帧动画：待机呼吸、东张西望、开心跃动、害羞、傲娇生气、受惊炸毛、打喷嚏、哈欠、
犯困、睡觉、睡眼惺忪、吃小鱼干、喝奶茶、伸懒腰、女仆礼仪、哼歌、漂浮踏步、360° 转圈、
被拖拽悬空、认真工作（带笔记本）、敲桌子、跳起、甩尾巴。

## 文件

```
deepseek-pet/
├─ pet.py              主程序（Tk 透明窗口 + 动画播放 + 交互 + 存档）
├─ assets/
│  ├─ anim/            动画帧包（每个动作一个 .bin + manifest.json）
│  ├─ pet.ico          图标
│  └─ actions.png      动作预览图
├─ build_anims.py      从源素材重建 anim/（一般不用跑）
└─ verify.py           动作自检截图脚本（开发用）
```

存档在 `%APPDATA%\DeepSeekPet\state.json`（饱食度 / 心情 / 亲密度 / 位置 / 累计陪伴时长）。

## 安装 / 卸载

```powershell
# 建桌面快捷方式「小鲸鱼娘」+ 开机启动（已执行过，可重复执行）
D:\python\python.exe pet.py --install

# 只启动
D:\python\pythonw.exe pet.py

# 移除快捷方式
D:\python\python.exe pet.py --uninstall
```

开机自启也可以在右键菜单里勾选/取消。

## 依赖

- Windows 10/11
- Python 3.9+（`D:\python\python.exe`），需要 `pillow`
- 自动跟随系统 DPI（150% 缩放下也是清晰的物理像素）
- 体型缩放系数在 pet.py 里的 self.zoom = 0.72，改大改小都行

## 素材来源

角色动画来自开源项目 **dsh-whale-girl-pet**（MIT License，npm 包 `dsh-whale-girl-pet`），
本项目把其中的 webm 逐帧解码、裁切后重新打包成 WebP 帧包，并重写了桌面端运行时。
如需商用请自行确认素材授权。
