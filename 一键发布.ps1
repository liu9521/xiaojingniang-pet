# 一键发布到 GitHub
# 用法：右键「使用 PowerShell 运行」，或在本目录执行  .\一键发布.ps1
# 需要先准备一个 GitHub token（只勾 Contents: Read and write，7 天过期）
# 生成地址：https://github.com/settings/personal-access-tokens/new

param(
    [string]$Repo = "xiaojingniang-pet",
    [string]$Tag = "v1.0.0",
    [string]$Exe = (Join-Path $PSScriptRoot "..\..\dist\小鲸鱼娘-安装程序.exe")
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

function Fail($msg) { Write-Host "`n✗ $msg" -ForegroundColor Red; Read-Host "按回车退出"; exit 1 }
function Step($msg) { Write-Host "`n→ $msg" -ForegroundColor Cyan }
function Ok($msg)   { Write-Host "  ✓ $msg" -ForegroundColor Green }

Write-Host "=== 小鲸鱼娘 · 发布到 GitHub ===" -ForegroundColor Magenta
Write-Host "仓库目录: $PSScriptRoot"
if (-not (Test-Path $Exe)) { Fail "找不到安装包：$Exe" }
$exeMB = [math]::Round((Get-Item $Exe).Length/1MB,1)
Write-Host "安装包: $Exe ($exeMB MB)"

$user = Read-Host "`nGitHub 用户名"
if (-not $user) { Fail "用户名不能为空" }

$sec = Read-Host "GitHub token（粘贴后回车，输入不回显）" -AsSecureString
$bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($sec)
try   { $token = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr) }
finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr) }
if (-not $token) { Fail "token 不能为空" }

$api = "https://api.github.com"
$headers = @{
    Authorization          = "Bearer $token"
    Accept                 = "application/vnd.github+json"
    "User-Agent"           = "xiaojingniang-publish"
    "X-GitHub-Api-Version" = "2022-11-28"
}

Step "验证 token"
try {
    $me = Invoke-RestMethod -Uri "$api/user" -Headers $headers -Method Get
    Ok "已登录：$($me.login)"
} catch { Fail "token 无效或权限不足：$($_.Exception.Message)" }
$user = $me.login

Step "检查仓库 $user/$Repo"
$repoExists = $true
try   { Invoke-RestMethod -Uri "$api/repos/$user/$Repo" -Headers $headers -Method Get | Out-Null; Ok "仓库已存在" }
catch { $repoExists = $false }

if (-not $repoExists) {
    Step "创建仓库"
    $body = @{
        name        = $Repo
        description = "一只住在 Windows 桌面上的蓝发鲸鱼女仆桌宠（DeepSeek Harness 快捷入口）"
        private     = $false
        has_issues  = $true
    } | ConvertTo-Json
    try { Invoke-RestMethod -Uri "$api/user/repos" -Headers $headers -Method Post -Body $body -ContentType "application/json" | Out-Null; Ok "已创建 $Repo" }
    catch { Fail "创建仓库失败：$($_.Exception.Message)" }
}

Step "推送代码"
Push-Location $PSScriptRoot
try {
    git remote remove origin 2>$null | Out-Null
    git remote add origin "https://github.com/$user/$Repo.git" 2>$null | Out-Null
    git branch -M main 2>$null | Out-Null
    # token 只用于这一次推送，不写进 .git/config
    $pushUrl = "https://x-access-token:$token@github.com/$user/$Repo.git"
    $out = git push $pushUrl "HEAD:main" --force 2>&1
    if ($LASTEXITCODE -ne 0) { $out | ForEach-Object { Write-Host "    $_" }; Fail "推送失败（见上方 git 输出）" }
    Ok "已推送到 main"
} finally { Pop-Location }

Step "创建 Release $Tag"
$relBody = @{
    tag_name = $Tag
    name     = "小鲸鱼娘 $Tag"
    body     = @"
首个公开版本。

- 23 组逐帧动画（待机 / 开心 / 害羞 / 生气 / 睡觉 / 吃东西 / 认真工作 …）
- 透明置顶窗口，拖拽自由摆放，松手即停
- 单击摸头，双击唤起本机 DeepSeek Harness，右键完整菜单
- 单文件安装包，无需 Python 环境

系统要求：Windows 10 / 11 64 位

安装包 SHA256：`$((Get-FileHash $Exe -Algorithm SHA256).Hash)
"@
    draft    = $false
    prerelease = $false
} | ConvertTo-Json

$release = $null
try {
    $release = Invoke-RestMethod -Uri "$api/repos/$user/$Repo/releases" -Headers $headers -Method Post -Body $relBody -ContentType "application/json"
    Ok "Release 已创建"
} catch {
    # 如果 tag 已存在，取现有 release
    try { $release = Invoke-RestMethod -Uri "$api/repos/$user/$Repo/releases/tags/$Tag" -Headers $headers; Ok "Release 已存在，沿用" }
    catch { Fail "创建 Release 失败：$($_.Exception.Message)" }
}

Step "上传安装包（约 66 MB，请稍候）"
$name = [System.Uri]::EscapeDataString("小鲸鱼娘-安装程序.exe")
$uploadUrl = "https://uploads.github.com/repos/$user/$Repo/releases/$($release.id)/assets?name=$name"
$upHeaders = @{
    Authorization = "Bearer $token"
    Accept        = "application/vnd.github+json"
    "User-Agent"  = "xiaojingniang-publish"
    "Content-Type" = "application/octet-stream"
}
try {
    Invoke-RestMethod -Uri $uploadUrl -Headers $upHeaders -Method Post -InFile $Exe -TimeoutSec 900 | Out-Null
    Ok "上传完成"
} catch { Fail "上传失败：$($_.Exception.Message)" }

Write-Host "`n=== 完成 ===" -ForegroundColor Green
Write-Host "仓库：https://github.com/$user/$Repo"
Write-Host "下载页：https://github.com/$user/$Repo/releases/tag/$Tag"
Write-Host "`n提示：发布后去 token 设置页把这次用的 token 撤销掉。" -ForegroundColor Yellow
Read-Host "`n按回车退出"
