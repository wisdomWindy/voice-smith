param(
    [Parameter(Mandatory = $true)][string]$Version,
    [string]$RuntimePack = "$PSScriptRoot\..\dist-assets\VoiceSmith-Runtime.7z",
    [string]$AssetsPack = "$PSScriptRoot\..\dist-assets\VoiceSmith-Offline-Assets.7z",
    [string]$OutDir = "$PSScriptRoot\..\dist-assets",
    [string]$Repo = 'wisdomWindy/voice-smith',
    [long]$ChunkBytes = 1800MB
)

$ErrorActionPreference = 'Stop'
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

function Split-Pack([string]$Path, [string]$Prefix, [string]$BaseUrl, [long]$Chunk) {
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
Split-Pack $RuntimePack 'runtime' $base $ChunkBytes
Split-Pack $AssetsPack 'assets' $base $ChunkBytes

