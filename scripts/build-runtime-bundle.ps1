param(
    [Parameter(Mandatory = $true)][string]$Version,
    [string]$ManifestDir = "$PSScriptRoot\..\dist-assets",
    [string]$OutFile = "$PSScriptRoot\..\dist-assets\runtime-bundle.json",
    [string]$Repo = 'wisdomWindy/voice-smith',
    [string]$Platform = 'windows-x64'
)

# Generate runtime-bundle.json: the entry point downloaded by the Tauri
# installer before it fetches the base/core/torch component manifests.
$ErrorActionPreference = 'Stop'
$base = "https://github.com/$Repo/releases/download/v$Version"
$manifestNames = [ordered]@{
    base  = 'runtime-base-manifest.json'
    core  = 'deps-core-manifest.json'
    torch = 'deps-torch-manifest.json'
}

$components = @()
foreach ($name in $manifestNames.Keys) {
    $fileName = $manifestNames[$name]
    $path = Join-Path $ManifestDir $fileName
    if (!(Test-Path $path)) { throw "missing component manifest: $path" }
    $manifest = Get-Content $path -Raw | ConvertFrom-Json
    if (!$manifest.sha256 -or $manifest.sha256 -notmatch '^[0-9a-fA-F]{64}$') {
        throw "$fileName has an invalid sha256"
    }
    if (!$manifest.parts -or $manifest.parts.Count -lt 1) {
        throw "$fileName has no parts"
    }
    $size = if ($manifest.size) { [long]$manifest.size } else { [long](($manifest.parts | Measure-Object -Property size -Sum).Sum) }
    if ($size -le 0) { throw "$fileName has no size" }
    $components += [ordered]@{
        name     = $name
        manifest = "$base/$fileName"
        sha256   = $manifest.sha256.ToLower()
        size     = $size
    }
}

$bundle = [ordered]@{
    version    = $Version
    platform   = $Platform
    components = $components
}
$parent = Split-Path -Parent $OutFile
if ($parent) { New-Item -ItemType Directory -Force -Path $parent | Out-Null }
$json = $bundle | ConvertTo-Json -Depth 6
[IO.File]::WriteAllText($OutFile, $json + "`n", [Text.UTF8Encoding]::new($false))
Write-Host "runtime-bundle=$OutFile components=$($components.Count) bytes=$((Get-Item $OutFile).Length)"
