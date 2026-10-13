"""T52 shape tests: the LSE API key is stored once as a DPAPI blob and loaded by start-api.ps1.

Text-level only: no PowerShell in CI, so this does NOT prove any .ps1 parses or runs.
That proof is the user's PC run (set-lse-key.ps1 -Status, API restart, equities refresh).
"""

import re
from pathlib import Path

DEPLOY = Path(__file__).resolve().parents[3] / "deploy"


def _read(name: str) -> str:
    return (DEPLOY / name).read_text(encoding="utf-8")


def _function_body(text: str, name: str) -> str:
    start = text.index(f"function {name}")
    nxt = text.find("\nfunction ", start + 1)
    return text[start:] if nxt == -1 else text[start:nxt]


def _dry_run_block(text: str) -> str:
    start = text.index("if ($DryRun) {\n    Write-Host")
    return text[start : text.index("exit 0", start)]


def test_set_lse_key_script_exists_and_uses_dpapi():
    text = _read("set-lse-key.ps1")
    assert "ConvertFrom-SecureString" in text
    assert "-Key " not in text and "-SecureKey" not in text, "must use DPAPI (no explicit key)"


def test_set_lse_key_validates_length_and_characters():
    text = _read("set-lse-key.ps1")
    assert "$minLength = 20" in text
    assert "$plain.Length -lt $minLength" in text
    assert "$plain -match '[\\s''\"]'" in text
    # The invalid branch reports only the length and stores nothing.
    invalid = text[text.index("$plain.Length -lt $minLength") : text.index("New-Item")]
    assert "exit 1" in invalid
    assert "Set-Content" not in invalid


def test_set_lse_key_has_modes():
    text = _read("set-lse-key.ps1")
    for switch in ("[switch]$FromClipboard", "[switch]$Prompt", "[switch]$Status", "[switch]$Remove"):
        assert switch in text
    assert "Get-Clipboard" in text
    assert "Read-Host -Prompt 'LSE API key (input hidden)' -AsSecureString" in text
    assert "Set-Clipboard -Value ' '" in text


def test_key_value_never_printed_or_written_in_plain():
    for name in ("set-lse-key.ps1", "start-api.ps1", "_common.ps1"):
        for line in _read(name).splitlines():
            if re.search(r"Write-(Host|Output|MySiteLog|Verbose|Warning)|Out-File|Set-Content|Add-Content", line):
                assert "$plain" not in line, f"{name}: {line.strip()}"
                assert "LSE_API_KEY" not in line or "Get-LseKeySource" in line, f"{name}: {line.strip()}"


def test_key_file_is_under_localappdata_not_repo():
    common = _read("_common.ps1")
    assert "$script:MySiteHome = Join-Path $env:LOCALAPPDATA 'my_site'" in common
    assert "$script:LseKeyPath = Join-Path $script:MySiteHome 'lse-api-key.dat'" in common
    assert "RepoRoot" not in _function_body(common, "Import-LseApiKey")
    assert "RepoRoot" not in _read("set-lse-key.ps1")


def test_start_api_loads_key_via_dpapi_and_env_first():
    common = _read("_common.ps1")
    body = _function_body(common, "Import-LseApiKey")
    assert "ConvertTo-SecureString -String $blob" in body
    assert "-AsPlainText" not in body
    assert "Get-Content" not in body
    source = _function_body(common, "Get-LseKeySource")
    assert source.index("$env:LSE_API_KEY") < source.index("LseKeyPath")
    assert "could not read the LSE key file (re-run deploy\\set-lse-key.ps1)" in body
    for msg in ("LSE key: from environment", "LSE key: from key file", "LSE key: not set"):
        assert msg in body
    api = _read("start-api.ps1")
    assert api.index("Import-LseApiKey") < api.index("& $config.UvPath @apiArgs")


def test_dry_run_does_not_decrypt_key():
    api = _read("start-api.ps1")
    dry = _dry_run_block(api)
    assert "Get-LseKeySource" in dry
    assert "ConvertTo-SecureString" not in dry
    assert "Import-LseApiKey" not in dry
    assert api.index("Import-LseApiKey") > api.index("if ($DryRun) {\n    Write-Host")
    assert "ConvertTo-SecureString" not in _function_body(_read("_common.ps1"), "Get-LseKeySource")


def test_changed_deploy_files_are_ascii():
    for name in ("set-lse-key.ps1", "start-api.ps1", "_common.ps1"):
        assert _read(name).isascii(), name
    readme = _read("README.md")
    section = readme[readme.index("## LSE API key") : readme.index("## After downtime")]
    assert section.isascii()
