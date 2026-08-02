[CmdletBinding()]
param(
    [string]$Destination = (Join-Path $PSScriptRoot "Models\yolov3-10.onnx")
)

$ErrorActionPreference = "Stop"
$ModelUrl = "https://github.com/onnx/models/raw/refs/heads/main/validated/vision/object_detection_segmentation/yolov3/model/yolov3-10.onnx"
$ExpectedSha256 = "1f4613c3d04416dfd2c1960b8737aa5292994238dfecbe9c1ee7147e9a92439f"
$Destination = [System.IO.Path]::GetFullPath($Destination)
$DestinationDirectory = Split-Path -Parent $Destination
$Temporary = "$Destination.download"

New-Item -ItemType Directory -Force -Path $DestinationDirectory | Out-Null

if (Test-Path $Destination) {
    $CurrentHash = (Get-FileHash -Algorithm SHA256 -Path $Destination).Hash.ToLowerInvariant()
    if ($CurrentHash -eq $ExpectedSha256) {
        Write-Host "Verified existing model: $Destination"
        exit 0
    }
}

try {
    Write-Host "Downloading pinned YOLOv3 model (about 236 MB)..."
    Invoke-WebRequest -Uri $ModelUrl -OutFile $Temporary
    $DownloadedHash = (Get-FileHash -Algorithm SHA256 -Path $Temporary).Hash.ToLowerInvariant()
    if ($DownloadedHash -ne $ExpectedSha256) {
        throw "Model checksum mismatch. Expected $ExpectedSha256, received $DownloadedHash."
    }
    Move-Item -Force -Path $Temporary -Destination $Destination
    Write-Host "Downloaded and verified: $Destination"
}
finally {
    if (Test-Path $Temporary) {
        Remove-Item -Force $Temporary
    }
}
