$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$envPath = Join-Path $projectRoot '.env'
if (Test-Path -LiteralPath $envPath) { Write-Host '.env already exists; no credentials changed.'; exit 0 }
function New-LocalSecret {
  $bytes = New-Object byte[] 32
  $generator = [System.Security.Cryptography.RandomNumberGenerator]::Create()
  try { $generator.GetBytes($bytes) } finally { $generator.Dispose() }
  return ([BitConverter]::ToString($bytes)).Replace('-', '').ToLowerInvariant()
}
$template = [System.IO.File]::ReadAllText((Join-Path $projectRoot '.env.example'))
$template = [regex]::Replace($template, "(?m)^POSTGRES_PASSWORD=\r?$", "POSTGRES_PASSWORD=$(New-LocalSecret)")
$template = $template.Replace("AUTH_MODE=jwt", "AUTH_MODE=development")
$template = [regex]::Replace($template, "(?m)^DEV_AUTH_TOKEN=\r?$", "DEV_AUTH_TOKEN=$(New-LocalSecret)")
[System.IO.File]::WriteAllText($envPath, $template)
Write-Host 'Created .env with random local credentials and explicit development auth. Secrets were not printed.'
