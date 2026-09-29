# my_site deploy config (example). Data only: loaded with Import-PowerShellDataFile,
# which never executes code.
#
# Copy this file OUT of the repo to:
#     $env:LOCALAPPDATA\my_site\deploy.psd1
# and edit the paths there. Nothing private belongs in this file, and none is needed:
# Tailscale sign-in happens in the Tailscale app, not here.
@{
    # Absolute path of this repo on the PC, e.g. (Get-Location).Path from the repo root.
    RepoRoot         = 'C:\Users\you\my_site'

    # Absolute tool paths. Task Scheduler ignores your shell PATH, so use `where.exe uv`
    # and `where.exe pnpm` to find them.
    UvPath           = 'C:\Users\you\.local\bin\uv.exe'
    PnpmPath         = 'C:\Users\you\AppData\Roaming\npm\pnpm.cmd'

    # Tailscale CLI. `ip -4` on it must print your 100.x.y.z address.
    TailscaleExe     = 'C:\Program Files\Tailscale\tailscale.exe'

    # Ports on the Tailscale address.
    ApiPort          = 8000
    WebPort          = 3000

    # How long the launchers wait for a Tailscale IPv4 at logon before giving up (seconds).
    MaxWaitSeconds   = 300

    # Stage A auto-resume: `git pull --ff-only` when the API starts. Never merges,
    # never forces; a refusal is logged and the app still starts.
    AutoPull         = $true

    # Extra browser origins allowed by the API (CORS). The launcher always allows
    # http://<tailscale-ip>:<WebPort>. Add a MagicDNS origin here if you use one,
    # e.g. @('http://my-pc.tail1234.ts.net:3000'). No trailing slash.
    ExtraCorsOrigins = @()

    # Optional overrides. Leave empty on the PC that already holds the caches:
    # the defaults (api\data\cache and api\data\watchlist.json in RepoRoot) are correct.
    CacheRoot        = ''
    WatchlistPath    = ''
}
