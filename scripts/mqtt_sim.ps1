# Start the MQTT live-data module and wire its topics into the API.
#   .\scripts\mqtt_sim.ps1            # publish + assign simulated topics
#   .\scripts\mqtt_sim.ps1 down
#   .\scripts\mqtt_sim.ps1 logs
# The main stack must already be up (docker compose up -d).
param(
  [ValidateSet("up", "down", "logs")]
  [string]$Action = "up"
)
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

$Api = if ($env:API) { $env:API } else { "http://localhost:8000" }
$Pass = if ($env:DEMO_PASSCODE) { $env:DEMO_PASSCODE } else { "hmt-demo" }
$BrokerHost = if ($env:MQTT_BROKER_HOST) { $env:MQTT_BROKER_HOST } else { "mosquitto" }

if ($Action -eq "down") {
  docker compose --profile mqtt-sim stop mqtt-sim
  exit $LASTEXITCODE
}
if ($Action -eq "logs") {
  docker compose --profile mqtt-sim logs -f mqtt-sim
  exit $LASTEXITCODE
}

docker compose --profile mqtt-sim up -d --build mqtt-sim
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "Waiting for API at $Api ..."
$ready = $false
foreach ($i in 1..40) {
  try {
    Invoke-RestMethod "$Api/api/v1/health" | Out-Null
    $ready = $true
    break
  } catch {
    Start-Sleep -Seconds 2
  }
}
if (-not $ready) {
  Write-Error "API not reachable. Start the stack first: docker compose up -d"
  exit 1
}

$login = Invoke-RestMethod -Method Post -Uri "$Api/api/v1/auth/login" -ContentType "application/json" `
  -Body (@{ username = "mission-control"; passcode = $Pass } | ConvertTo-Json)
$headers = @{ Authorization = "Bearer $($login.access_token)" }
$result = Invoke-RestMethod -Method Post -Uri "$Api/api/v1/mqtt/sim-pipeline" -Headers $headers `
  -ContentType "application/json" -Body (@{ host = $BrokerHost; port = 1883 } | ConvertTo-Json)
Write-Host "Pipeline wired: $($result.installed.Count) simulated topics, broker $($result.status.host)"
Write-Host "Open Habitat sensors. Every reading is labelled simulated."
