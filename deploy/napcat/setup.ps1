<#
.SYNOPSIS
  Mini-Drop NapCat QQ 机器人一键安装脚本

.DESCRIPTION
  自动下载、配置 NapCat（OneBot v11 兼容的 QQ 机器人框架），
  与 Mini-Drop 的 ChatOps qqbot 模块无缝对接。

  执行后只需：
    1. 运行 deploy\napcat\start-qq.cmd 扫码登录 QQ
    2. 在 Mini-Drop .env 中填入 QQ 机器人配置
    3. 启动 micro-drop serve

.PARAMETER InstallDir
  NapCat 安装目录，默认为当前目录

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File setup.ps1
#>

param(
    [string]$InstallDir = "$PSScriptRoot"
)

$ErrorActionPreference = "Stop"
$NAP_VER = "v4.18.6"
$NAP_DOWNLOAD = "https://github.com/NapNeko/NapCatQQ/releases/download/$NAP_VER/NapCat.Shell.Windows.OneKey.zip"
$ZIP_FILE = "$InstallDir\NapCat.OneKey.zip"

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  Mini-Drop × NapCat QQ 机器人安装向导" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# 1. 下载
Write-Host "[1/3] 下载 NapCat $NAP_VER …" -ForegroundColor Yellow
if (Test-Path $ZIP_FILE) {
    Write-Host "  安装包已存在，跳过下载" -ForegroundColor Green
} else {
    try {
        Invoke-WebRequest -Uri $NAP_DOWNLOAD -OutFile $ZIP_FILE -TimeoutSec 120
        Write-Host "  下载完成: $ZIP_FILE" -ForegroundColor Green
    } catch {
        Write-Host "  下载失败! 请手动下载并解压到 $InstallDir" -ForegroundColor Red
        Write-Host "  $NAP_DOWNLOAD" -ForegroundColor Gray
        exit 1
    }
}

# 2. 解压
Write-Host "[2/3] 解压安装包 …" -ForegroundColor Yellow
try {
    Expand-Archive -Path $ZIP_FILE -DestinationPath $InstallDir -Force
    Write-Host "  解压完成" -ForegroundColor Green
} catch {
    Write-Host "  解压失败! 请手动解压 $ZIP_FILE 到 $InstallDir" -ForegroundColor Red
    exit 1
}

# 3. 创建启动脚本
Write-Host "[3/3] 生成启动脚本和配置模板 …" -ForegroundColor Yellow

# 一键启动 + 登录的 cmd 脚本
$startCmd = @'
@echo off
chcp 65001 >nul
title NapCat QQ Bot

echo.
echo ============================================
echo   NapCat QQ 机器人启动中…
echo ============================================
echo.
echo 如果弹出 QQ 登录窗口，请扫码登录。
echo 登录成功后 NapCat 将在后台运行。
echo.
echo OneBot HTTP API 地址: http://localhost:5700
echo.
echo 按 Ctrl+C 或关闭此窗口停止机器人。
echo ============================================
echo.

if exist bootmain\napcat.bat (
    cd bootmain
    call napcat.bat
) else (
    echo [错误] 未找到 bootmain\napcat.bat，请确认解压完整
    echo 预期路径: %cd%\bootmain\napcat.bat
    pause
)
'@
$startCmd | Out-File -FilePath "$InstallDir\start-qq.cmd" -Encoding UTF8

# 快速重新登录脚本（跳过框架更新）
$quickCmd = @'
@echo off
chcp 65001 >nul
title NapCat QQ Bot (Quick)
if exist bootmain\napcat.quick.bat (
    cd bootmain
    call napcat.quick.bat
) else (
    echo [错误] 未找到 bootmain\napcat.quick.bat
    pause
)
'@
$quickCmd | Out-File -FilePath "$InstallDir\start-qq-quick.cmd" -Encoding UTF8

Write-Host "  启动脚本已生成: start-qq.cmd" -ForegroundColor Green
Write-Host "  快速登录脚本:    start-qq-quick.cmd" -ForegroundColor Green

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  安装完成!" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  接下来请执行以下步骤:" -ForegroundColor White
Write-Host ""
Write-Host "  1. 运行 start-qq.cmd 并扫码登录 QQ" -ForegroundColor Yellow
Write-Host "  2. 在 Mini-Drop .env 中添加:" -ForegroundColor Yellow
Write-Host ""
Write-Host "     MINI_DROP_CHATOPS_ENABLED=1" -ForegroundColor Gray
Write-Host "     MINI_DROP_CHATOPS_PROVIDER=qqbot" -ForegroundColor Gray
Write-Host "     MINI_DROP_CHATOPS_WEBHOOK_URL=http://localhost:5700" -ForegroundColor Gray
Write-Host "     MINI_DROP_QQBOT_TARGET_TYPE=group" -ForegroundColor Gray
Write-Host "     MINI_DROP_QQBOT_TARGET_ID=你的群号" -ForegroundColor Gray
Write-Host ""
Write-Host "  3. 启动 Mini-Drop: micro-drop serve" -ForegroundColor Yellow
Write-Host "  4. 测试连接: micro-drop chatops-test" -ForegroundColor Yellow
Write-Host ""
Write-Host "  详细文档: deploy/napcat/README.md" -ForegroundColor Gray
Write-Host ""
pause
