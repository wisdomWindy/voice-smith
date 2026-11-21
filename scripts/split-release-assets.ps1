param(
    [Parameter(Mandatory = $true)][string]$Version,
    [string]$RuntimeBasePack = "$PSScriptRoot\..\dist-assets\VoiceSmith-Runtime-base.7z",
    [string]$DepsCorePack = "$PSScriptRoot\..\dist-assets\VoiceSmith-Deps-core.7z",
    [string]$DepsTorchPack = "$PSScriptRoot\..\dist-assets\VoiceSmith-Deps-torch.7z",
    [string]$AssetsPack = "$PSScriptRoot\..\dist-assets\VoiceSmith-Offline-Assets.7z",
    [string]$OutDir = "$PSScriptRoot\..\dist-assets",
    [string]$Repo = 'wisdomWindy/voice-smith',
    [string]$Platform = 'windows-x64',
    [long]$ChunkBytes = 1800MB,
    [switch]$SkipAssets,
    [switch]$SkipBundle
)

$ErrorActionPreference = 'Stop'
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

function Split-Pack([string]$Path, [string]$Prefix, [string]$BaseUrl, [long]$Chunk) {
    if (!(Test-Path $Path)) { throw "pack not found: $Path" }
    Get-ChildItem $OutDir -Filter "$Prefix.part*" -File -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue
    $hash = (Get-FileHash $Path -Algorithm SHA256).Hash.ToLower()
    $size = (Get-Item $Path).Length
    $buffer = New-Object byte[] (8MB)
    $input = [IO.File]::OpenRead($Path)
    try {
        $index = 1
        $parts = @()
        while ($input.Position -lt $input.Length) {
            $partName = '{0}.part{1:D2}' -f $Prefix, $index
            $partPath = Join-Path $OutDir $partName
            $out = [IO.File]::Create($partPath)
            try {
                $left = [Math]::Min($Chunk, $input.Length - $input.Position)
                while ($left -gt 0) {
                    $want = [Math]::Min($buffer.Length, $left)
                    $read = $input.Read($buffer, 0, $want)
                    if ($read -le 0) { break }
                    $out.Write($buffer, 0, $read)
                    $left -= $read
                }
            } finally { $out.Close() }
            $partSize = (Get-Item $partPath).Length
            $parts += [ordered]@{
                url = "$BaseUrl/$partName"
                file = $partName
                size = $partSize
            }
            $index++
        }
    } finally { $input.Close() }
    $manifest = [ordered]@{
        version = $Version
        sha256 = $hash
        size = $size
        parts = $parts
    }
    $manifestPath = Join-Path $OutDir ($Prefix + '-manifest.json')
    [IO.File]::WriteAllText($manifestPath, ($manifest | ConvertTo-Json -Depth 5), [Text.UTF8Encoding]::new($false))
    Write-Host "$Prefix sha256=$hash parts=$($parts.Count) manifest=$manifestPath"
}

$base = "https://github.com/$Repo/releases/download/v$Version"
Split-Pack $RuntimeBasePack 'runtime-base' $base $ChunkBytes
Split-Pack $DepsCorePack 'deps-core' $base $ChunkBytes
Split-Pack $DepsTorchPack 'deps-torch' $base $ChunkBytes
if (!$SkipAssets) {
    Split-Pack $AssetsPack 'assets' $base $ChunkBytes
}
if (!$SkipBundle) {
    & "$PSScriptRoot\build-runtime-bundle.ps1" -Version $Version -ManifestDir $OutDir -OutFile (Join-Path $OutDir 'runtime-bundle.json') -Repo $Repo -Platform $Platform
}
