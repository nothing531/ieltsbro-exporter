param(
    [string] $Profile,
    [string] $Out,
    [switch] $CheckOnly
)

$ErrorActionPreference = 'Stop'
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

$commands = @('py', 'python', 'python3')
$python = $null
foreach ($name in $commands) {
    $command = Get-Command $name -ErrorAction SilentlyContinue
    if ($command) {
        $python = $command.Source
        break
    }
}

if (-not $python) {
    throw '未找到 Python 3。请先从 https://www.python.org/downloads/ 安装 Python。'
}

$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$outDir = if ($Out) {
    $Out
} else {
    Join-Path (Get-Location) "ieltsbro-export-$stamp"
}
$arguments = @((Join-Path $scriptDir 'ieltsbro_export.py'), '--out', $outDir)

if ($Profile) {
    $arguments += @('--profile', $Profile)
}

if ($CheckOnly) {
    $arguments += '--check-only'
}

& $python @arguments
if ($LASTEXITCODE -ne 0) {
    throw "导出失败，退出码：$LASTEXITCODE"
}

if ($CheckOnly) {
    Write-Host "`n登录态与只读接口验证成功。" -ForegroundColor Green
} else {
    Write-Host "`n已保存到：$outDir" -ForegroundColor Green
}
