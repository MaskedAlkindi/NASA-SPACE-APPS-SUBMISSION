# HEALTH-01: connect this PC to a big GPU server (Ollama + fine-tuning trainer). See docs/llm/GPU_SERVER.md.
#   .\scripts\gpu_server.ps1 -Server user@1.2.3.4 -Action setup     # copy repo + datasets, start containers
#   .\scripts\gpu_server.ps1 -Server user@1.2.3.4 -Action tunnel    # keep open while you use it
#   .\scripts\gpu_server.ps1 -Server user@1.2.3.4 -Action pull      # copy finished runs back (optional)
param([Parameter(Mandatory)][string]$Server, [ValidateSet("setup", "tunnel", "pull")][string]$Action = "tunnel",
      [string]$RemoteDir = "~/health01")
$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
$envFile = Join-Path $root ".env"

function Get-Token {
    $line = if (Test-Path $envFile) { Select-String -Path $envFile -Pattern '^HMT_TRAINER_TOKEN=(.+)$' } else { $null }
    if ($line) { return $line.Matches[0].Groups[1].Value }
    $t = -join ((48..57) + (97..122) | Get-Random -Count 40 | ForEach-Object { [char]$_ })
    Add-Content $envFile "`nHMT_TRAINER_TOKEN=$t`nHMT_LLM_TRAINER_URL=http://host.docker.internal:8601`nOLLAMA_BASE_URL_DOCKER=http://host.docker.internal:11435"
    Write-Host "Added trainer token and tunnel URLs to .env"
    return $t
}

switch ($Action) {
    "setup" {
        $token = Get-Token
        Push-Location $root
        $tar = Join-Path $env:TEMP "health01-src.tar"
        git archive --format=tar -o $tar HEAD
        tar -rf $tar data/llm/corpus data/llm/datasets data/llm/rag
        Pop-Location
        ssh $Server "mkdir -p $RemoteDir"
        scp $tar "${Server}:$RemoteDir/src.tar"
        ssh $Server "cd $RemoteDir && tar -xf src.tar && rm src.tar && mkdir -p data/llm/runs data/llm/jobs && cd deploy/gpu-server && HMT_TRAINER_TOKEN=$token docker compose up -d --build"
        Write-Host "Server is up. Next: .\scripts\gpu_server.ps1 -Server $Server -Action tunnel"
    }
    "tunnel" {
        Write-Host "Tunnel open: Ollama -> localhost:11435, trainer -> localhost:8601. Ctrl+C to close."
        ssh -N -o ServerAliveInterval=30 -o ExitOnForwardFailure=yes -L 11435:127.0.0.1:11434 -L 8601:127.0.0.1:8600 $Server
    }
    "pull" {
        scp -r "${Server}:$RemoteDir/data/llm/runs/*" (Join-Path $root "data/llm/runs/")
        Write-Host "Runs copied to data/llm/runs"
    }
}
