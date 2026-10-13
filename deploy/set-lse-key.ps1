# Store the LSE API key once for the my_site API, protected by Windows DPAPI.
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File deploy\set-lse-key.ps1 [-FromClipboard] [-Prompt] [-Status] [-Remove]
#
# Default (or -FromClipboard): read the key from the clipboard, then clear the clipboard.
# -Prompt: type or paste the key at a hidden prompt instead.
# -Status: say whether the key file is present and how many characters it holds (never the value).
# -Remove: delete the key file.
#
# The file is %LOCALAPPDATA%\my_site\lse-api-key.dat, written with ConvertFrom-SecureString:
# only this Windows user on this PC can decrypt it. It is outside the repo. The key is never
# printed, logged or written anywhere else. Restart the API afterwards (deploy\README.md).
#
# UNVERIFIED IN CI: written without PowerShell available; run -Status on the PC to check.
param(
    [switch]$FromClipboard,
    [switch]$Prompt,
    [switch]$Status,
    [switch]$Remove
)

. "$PSScriptRoot\_common.ps1"

$keyPath = $script:LseKeyPath
$minLength = 20

function ConvertFrom-LseSecure {
    param([Parameter(Mandatory)][System.Security.SecureString]$Secure)
    $bstr = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($Secure)
    try {
        return [System.Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
    } finally {
        [System.Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
    }
}

if ($Remove) {
    if (Test-Path -LiteralPath $keyPath) {
        Remove-Item -LiteralPath $keyPath -Force
        Write-Host "LSE key file removed: $keyPath"
    } else {
        Write-Host "LSE key file: absent (nothing to remove)"
    }
    exit 0
}

if ($Status) {
    if (-not (Test-Path -LiteralPath $keyPath)) {
        Write-Host "LSE key file: absent"
        exit 0
    }
    try {
        $blob = ([System.IO.File]::ReadAllText($keyPath)).Trim()
        $count = (ConvertFrom-LseSecure -Secure (ConvertTo-SecureString -String $blob)).Length
        Write-Host "LSE key file: present ($count chars)"
        exit 0
    } catch {
        Write-Host "LSE key file: present but unreadable for this user on this PC; re-run deploy\set-lse-key.ps1"
        exit 1
    }
}

if ($FromClipboard -and $Prompt) {
    Write-Host "Use either -FromClipboard or -Prompt, not both."
    exit 2
}

if ($Prompt) {
    $secureInput = Read-Host -Prompt 'LSE API key (input hidden)' -AsSecureString
    $plain = ConvertFrom-LseSecure -Secure $secureInput
} else {
    $plain = [string](Get-Clipboard -Raw)
}
if ($null -eq $plain) { $plain = '' }
$plain = $plain.Trim()

# Validate before storing anything. Report only the length, never the value.
if ($plain.Length -lt $minLength -or $plain -match '[\s''"]') {
    $length = $plain.Length
    $plain = $null
    Write-Host "Not stored: the key must be at least $minLength characters with no spaces, line breaks or quotes (got $length characters). Copy the key again and re-run."
    exit 1
}

if (-not (Test-Path -LiteralPath $script:MySiteHome)) {
    New-Item -ItemType Directory -Force -Path $script:MySiteHome | Out-Null
}
$blob = ConvertFrom-SecureString -SecureString (ConvertTo-SecureString -String $plain -AsPlainText -Force)
$plain = $null
Set-Content -LiteralPath $keyPath -Value $blob -Encoding Ascii

# Restrict the file to the current user. DPAPI already protects the content; this is extra.
$acl = 'not changed (DPAPI still protects the content)'
try {
    $null = & icacls $keyPath /inheritance:r /grant:r "$($env:USERDOMAIN)\$($env:USERNAME):(F)" 2>&1
    if ($LASTEXITCODE -eq 0) { $acl = 'current user only' }
} catch {
    $acl = 'not changed (DPAPI still protects the content)'
}

if (-not $Prompt) {
    Set-Clipboard -Value ' '
}
Write-Host "LSE key stored: $keyPath (DPAPI, this Windows user on this PC; file access: $acl)."
Write-Host "Restart the API to use it: Stop-ScheduledTask mysite-api; Start-ScheduledTask mysite-api"
exit 0
