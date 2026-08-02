[CmdletBinding()]
param(
    [ValidateSet("Debug", "Release")]
    [string]$Configuration = "Release",

    [ValidateSet("win-x64", "win-arm64")]
    [string]$Runtime = "win-x64"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = $PSScriptRoot
$TestProject = Join-Path $ProjectRoot "FocusFloat.Core.Tests\FocusFloat.Core.Tests.csproj"
$AppProject = Join-Path $ProjectRoot "FocusFloat.Windows\FocusFloat.Windows.csproj"
$Platform = if ($Runtime -eq "win-arm64") { "ARM64" } else { "x64" }
$ArtifactRoot = Join-Path $ProjectRoot "artifacts"
$PublishDirectory = Join-Path $ArtifactRoot "FocusWith-Windows-$Runtime"
$Archive = "$PublishDirectory.zip"

dotnet restore $TestProject
dotnet test $TestProject --configuration $Configuration --no-restore

if (Test-Path $PublishDirectory) {
    Remove-Item -Recurse -Force $PublishDirectory
}
if (Test-Path $Archive) {
    Remove-Item -Force $Archive
}

dotnet publish $AppProject `
    --configuration $Configuration `
    --runtime $Runtime `
    --self-contained true `
    -p:Platform=$Platform `
    --output $PublishDirectory

Compress-Archive -Path (Join-Path $PublishDirectory "*") -DestinationPath $Archive
Write-Host "Built $Archive"
