<#>
.SYNOPSIS
    Orvima installer - installs Orvima CLI with MCP support
.DESCRIPTION
    Downloads the latest Orvima release wheel from GitHub and installs it.
    Detects uv/pipx/pip and uses the best available installer.
#>

param(
    [string]$Version = "latest",
    [switch]$Force,
    [switch]$NoMcp
)

$ErrorActionPreference = "Stop"

# Colors
$Green  = [ConsoleColor]::Green
$Yellow = [ConsoleColor]::Yellow
$Red    = [ConsoleColor]::Red
$Cyan   = [ConsoleColor]::Cyan

function Write-Color($msg, $color) {
    $orig = $Host.UI.RawUI.ForegroundColor
    $Host.UI.RawUI.ForegroundColor = $color
    Write-Host $msg
    $Host.UI.RawUI.ForegroundColor = $orig
}

function Get-LatestRelease {
    $api = "https://api.github.com/repos/Sachitt-AV-08/orvima/releases/latest"
    try {
        $resp = Invoke-RestMethod -Uri $api -Headers @{ "Accept" = "application/vnd.github.v3+json" }
        return $resp.tag_name
    } catch {
        Write-Color "Failed to fetch latest release: $($_.Exception.Message)" $Red
        return "v0.1.0"
    }
}

function Get-WheelUrl($tag) {
    $api = "https://api.github.com/repos/Sachitt-AV-08/orvima/releases/tags/$tag"
    try {
        $resp = Invoke-RestMethod -Uri $api -Headers @{ "Accept" = "application/vnd.github.v3+json" }
        $wheel = $resp.assets | Where-Object { $_.name -like "*.whl" } | Select-Object -First 1
        if ($wheel) { return $wheel.browser_download_url }
    } catch { }
    $version = $tag.TrimStart('v')
    return "https://github.com/Sachitt-AV-08/orvima/releases/download/$tag/orvima-$version-py3-none-any.whl"
}

Write-Color "╔══════════════════════════════════════════╗" $Cyan
Write-Color "║     Orvima Installer                     ║" $Cyan
Write-Color "║   The browser your AI drives             ║" $Cyan
Write-Color "╚══════════════════════════════════════════╝" $Cyan
Write-Host ""

if ($Version -eq "latest") {
    Write-Color "Fetching latest release..." $Yellow
    $Version = Get-LatestRelease
}
Write-Color "Target version: $Version" $Cyan

$hasUv    = (Get-Command uv -ErrorAction SilentlyContinue) -ne $null
$hasPipx  = (Get-Command pipx -ErrorAction SilentlyContinue) -ne $null
$hasPip   = (Get-Command pip -ErrorAction SilentlyContinue) -ne $null

if ($hasUv) {
    Write-Color "Found uv - using uv tool install" $Green
    if ($NoMcp) {
        & uv tool install "orvima @ git+https://github.com/Sachitt-AV-08/orvima.git@$Version"
    } else {
        & uv tool install "orvima[mcp] @ git+https://github.com/Sachitt-AV-08/orvima.git@$Version"
    }
} elseif ($hasPipx) {
    Write-Color "Found pipx - using pipx install" $Green
    if ($NoMcp) {
        & pipx install "orvima @ git+https://github.com/Sachitt-AV-08/orvima.git@$Version"
    } else {
        & pipx install "orvima[mcp] @ git+https://github.com/Sachitt-AV-08/orvima.git@$Version"
    }
} elseif ($hasPip) {
    Write-Color "Found pip - using pip install" $Green
    $wheelUrl = Get-WheelUrl $Version
    Write-Color "Downloading wheel: $wheelUrl" $Cyan
    if (-not $NoMcp) {
        & pip install "orvima[mcp] @ $wheelUrl"
    } else {
        & pip install "orvima @ $wheelUrl"
    }
} else {
    Write-Color "No installer found (uv/pipx/pip). Please install Python first." $Red
    exit 1
}

Write-Host ""
Write-Color "✓ Orvima installed successfully!" $Green
Write-Host ""
Write-Color "Quick start:" $Cyan
Write-Host "  orvima demo                    # Offline tour"
Write-Host "  orvima serve --mode real       # Launch API + UI at :8301"
Write-Host "  orvima run \"your goal\"         # Headless agent"
Write-Host ""
Write-Color "MCP config (Claude Desktop / Cursor / Copilot):" $Cyan
Write-Host @"
{
  "mcpServers": {
    "orvima": { "command": "orvima", "args": ["mcp", "--mode", "demo"], "type": "stdio" }
  }
}
"@