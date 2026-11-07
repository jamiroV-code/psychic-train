# SYNTHETIC EXAMPLE of %LOCALAPPDATA%\my_site\deploy.psd1 for the collector identity pool.
# Start from deploy\config.example.psd1 (same keys); the collector only adds CollectorQueriesPath.
# Data only: loaded with Import-PowerShellDataFile, which never executes code. No secret belongs here.
@{
    RepoRoot             = 'C:\Users\you\my_site'
    UvPath               = 'C:\Users\you\.local\bin\uv.exe'
    PnpmPath             = 'C:\Users\you\AppData\Roaming\npm\pnpm.cmd'
    TailscaleExe         = 'C:\Program Files\Tailscale\tailscale.exe'
    ApiPort              = 8000
    WebPort              = 3000
    MaxWaitSeconds       = 300
    AutoPull             = $true
    ExtraCorsOrigins     = @()
    CacheRoot            = ''
    WatchlistPath        = ''
    # Absolute PRIVATE query file outside RepoRoot (see private-layout.example.txt).
    CollectorQueriesPath = 'C:\MySitePrivate\config\attention_queries.private.json'
}
