[Console]::OutputEncoding = [Text.Encoding]::UTF8
# Avoid non-ASCII literals (powershell.exe reads .ps1 as ANSI): discover the folder with a wildcard.
$R = (Get-ChildItem 'F:\Software' -Directory -Filter 'JARV*' | Select-Object -First 1).FullName
$P = Join-Path $R '.venv\Scripts\python.exe'
$W = Join-Path $R 'platform\web\src'
Write-Output ("ROOT=" + $R)

function State($tag) {
  $types = Select-String -Path (Join-Path $W 'types.ts') -Pattern 'privacy_mode|wellbeing|widget_layout' -Quiet
  $client = Select-String -Path (Join-Path $W 'api\client.ts') -Pattern '/privacy|privacy_status' -Quiet
  $i18n = Select-String -Path (Join-Path $W 'i18n.ts') -Pattern 'privacy:' -Quiet
  $app = Select-String -Path (Join-Path $W 'App.tsx') -Pattern 'PrivacyWellnessCard' -Quiet
  $comp = Test-Path (Join-Path $W 'components\PrivacyWellnessCard.tsx')
  $main = Select-String -Path (Join-Path $W 'main.tsx') -Pattern 'Sentry' -Quiet
  Write-Output ("$tag types=$types client=$client i18n=$i18n app=$app comp=$comp main_sentry=$main")
}

State 'PRE '
foreach ($s in @('s1_types_client.py', 's2_component.py', 's3_app_i18n.py')) {
  Write-Output ("=== " + $s + " ===")
  $out = & $P (Join-Path $R ('tools_g\' + $s)) 2>&1 | Out-String
  Write-Output $out.TrimEnd()
  Write-Output ("EXIT=" + $LASTEXITCODE)
}
State 'POST'

Set-Location (Join-Path $R 'platform\web')
$b = npm run build 2>&1 | Out-String
Write-Output ("BUILD_EXIT=" + $LASTEXITCODE)
Write-Output (($b -split "`r?`n" | Select-Object -Last 14) -join "`n")
