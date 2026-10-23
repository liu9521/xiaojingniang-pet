# 发布指南 / How to publish

仓库内容已经整理好，按下面的步骤上传即可。**exe 不要提交进 git**（66 MB，超过 GitHub 单文件建议值），
放到各平台的「Release / 附件」里。

---

## 0. 上传前要补的两样

1. **收款码**：把二维码图片存成 `assets/donate-qr.png`（README 末尾已经引用这个路径）。
   - 建议 300×300 以上、干净的二维码截图
   - 不要用原始素材包里的 `qr-donate.png`，那是原作者 dsh-whale-girl-pet 的收款码
2. **示例图**：`assets/screenshots/` 下已有 `desktop.png` 和 `actions.png`，可直接用。

---

## 1. GitHub（首选）

**方式 A：网页上传（不用装工具）**

1. 注册 / 登录 <https://github.com>
2. 右上角 `+` → `New repository`
   - Repository name: `xiaojingniang-pet`
   - Description: `一只住在 Windows 桌面上的蓝发鲸鱼女仆桌宠`
   - 选 `Public`，**不要**勾选 Add a README / .gitignore（本地已有）
3. 进入空仓库 → `uploading an existing file` → 把本目录里**除 `.git` 外**的所有文件拖进去 → Commit
4. 左侧 `Releases` → `Create a new release`
   - Tag: `v1.0.0`，Title: `小鲸鱼娘 v1.0.0`
   - 附件拖入 `小鲸鱼娘-安装程序.exe`
   - 正文可写：`首个版本：23 组动作、透明置顶、双击唤起 DeepSeek Harness。`
   - Publish release

**方式 B：命令行**

```powershell
cd repo
git init
git add .
git commit -m "feat: 小鲸鱼娘桌宠 v1.0.0"
git branch -M main
git remote add origin https://github.com/<你的用户名>/xiaojingniang-pet.git
git push -u origin main
```

推送后到网页 Releases 上传 exe（或装 `gh` 后用
`gh release create v1.0.0 "..\小鲸鱼娘-安装程序.exe" -t "小鲸鱼娘 v1.0.0"`）。

> 若 `git push` 要求密码：GitHub 已不支持密码推送，需在
> Settings → Developer settings → Personal access tokens 生成 token，用 token 当密码。

---

## 2. Gitee（国内访问快）

1. <https://gitee.com> 注册并完成实名（发布 Release 需要）
2. 新建仓库 → 导入 GitHub 仓库，或直接 `git remote add gitee <地址>` 再 push
3. 仓库页 →「发行版」→ 新建发行版，上传 `小鲸鱼娘-安装程序.exe`
4. 注意：Gitee 对「打赏/收款」内容审核较严，二维码建议放在 README 最末，
   或单独 `DONATE.md`，避免整个仓库被判定为营销内容

---

## 3. GitCode / AtomGit（国内备选）

- <https://gitcode.com>（CSDN 系）
- <https://atomgit.com>（开放原子基金会）
- 两者都支持从 GitHub 一键导入；操作与 Gitee 类似。

---

## 4. SourceForge（老牌开源托管，适合放下载）

1. <https://sourceforge.net> 注册 → `Create Project`
2. 上传源码包 + 安装包到 Files
3. 优点：下载页对国外用户友好；缺点：界面老，国内访问一般

---

## 5. itch.io（独立作品发布，适合桌宠）

1. <https://itch.io> 注册 → `Upload new project`
2. Kind of project: `Tools`，Pricing: 可选 `$0 or donate`（自带打赏机制，比二维码更规范）
3. 上传 `小鲸鱼娘-安装程序.exe`，配图用 `assets/screenshots/`
4. 优点：桌宠/小工具受众合适，自带「自愿付费」按钮

---

## 6. 纯网盘（只做国内快速下载，不算开源站）

- 蓝奏云、123 云盘、阿里云盘：放 exe，README 里给链接
- 缺点：链接易失效、无法版本管理，仅作 GitHub 的镜像补充

---

## 发布检查清单

- [ ] `assets/donate-qr.png` 已放好，README 能正常显示
- [ ] `LICENSE` 与 `THIRD_PARTY.md` 保留（MIT 要求署名）
- [ ] Release 里上传了 exe，并在 README 下载表格中指向正确
- [ ] 仓库描述、Topics 填好（`desktop-pet`、`windows`、`deepseek`、`tkinter`）
- [ ] 首次发布后自己下载一次安装包，在干净目录跑一遍
- [ ] 记录 exe 的 SHA256 贴在 Release 说明里，方便别人校验：

```powershell
Get-FileHash "小鲸鱼娘-安装程序.exe" -Algorithm SHA256
```
