<#
 .SYNOPSIS
    Demo end-to-end del flujo de consenso (registro → freeze → seed → votos → resultado → bloque → reporte) usando PGPy.

 .REQUIREMENTS
    - Docker/Compose con el backend levantado (node_a en http://127.0.0.1:8001).
    - Python 3.11 y PGPy instalados (requirements.txt del proyecto).
    - Claves en .\keys\ (node_a/b/c) y script scripts\sign_text.py existente.
#>

param(
    [string]$Api = "http://127.0.0.1:8001",
    [int]$Turn = 0,
    [int]$Tokens = 100,
    [string]$SeedHex = "",
    [string]$BlockHash = "abcd1234",
    [switch]$DoReport
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Get-FileText {
    param([string]$Path)
    return [System.IO.File]::ReadAllText((Resolve-Path $Path), [System.Text.Encoding]::UTF8)
}

function Get-PGPSignature {
    param([string]$PrivPath, [string]$TextToSign)
    return [string]::Join("`n", (python scripts\sign_text.py $PrivPath $TextToSign))
}

function IpToInt([string]$ip) {
    $p = $ip.Split('.').ForEach([int])
    return ($p[0] -shl 24) -bor ($p[1] -shl 16) -bor ($p[2] -shl 8) -bor $p[3]
}

$nodes = @(
    @{ id="node_a"; ip="172.28.0.11"; priv="keys\node_a_priv.asc"; pub="keys\node_a_pub.asc" },
    @{ id="node_b"; ip="172.28.0.12"; priv="keys\node_b_priv.asc"; pub="keys\node_b_pub.asc" },
    @{ id="node_c"; ip="172.28.0.13"; priv="keys\node_c_priv.asc"; pub="keys\node_c_pub.asc" }
)

# Validaciones mínimas
foreach ($n in $nodes) {
    foreach ($k in @("priv","pub")) {
        if (-not (Test-Path -LiteralPath $n[$k])) {
            throw "Falta archivo: $($n[$k])"
        }
    }
}
if (-not (Test-Path -LiteralPath "scripts\sign_text.py")) {
    throw "Falta scripts\sign_text.py (ver README para su contenido)."
}

Write-Host "API target: $Api" -ForegroundColor Cyan
Write-Host "Turno: $Turn  Tokens: $Tokens  BlockHash: $BlockHash" -ForegroundColor Cyan

# 1) REGISTER + FREEZE
foreach ($n in $nodes) {
    $pub = Get-FileText $n.pub
    $payload = "{0}|{1}|{2}" -f $n.id, $n.ip, $pub
    $sig = Get-PGPSignature $n.priv $payload

    $body = @{ nodeId=$n.id; ip=$n.ip; publicKeyArmored=$pub; signature=$sig } | ConvertTo-Json -Depth 6
    $r = Invoke-RestMethod -Uri "$Api/network/register" -Method Post -ContentType "application/json" -Body $body
    Write-Host ("REGISTER {0}: {1}" -f $n.id, ($r | ConvertTo-Json -Compress)) -ForegroundColor Green

    $sigFr = Get-PGPSignature $n.priv ("{0}|{1}" -f $n.id, $Tokens)
    $body = @{ nodeId=$n.id; tokens=$Tokens; signature=$sigFr } | ConvertTo-Json
    $r = Invoke-RestMethod -Uri "$Api/tokens/freeze" -Method Post -ContentType "application/json" -Body $body
    Write-Host ("FREEZE   {0}: {1}" -f $n.id, ($r | ConvertTo-Json -Compress)) -ForegroundColor Green
}

# 2) Determinar líder por rotación IP (descendente)
$sorted = $nodes | Sort-Object @{Expression={ IpToInt $_.ip }} -Descending
$leader = $sorted[ $Turn % $sorted.Count ].id
Write-Host "Líder de rotación turno $Turn => $leader" -ForegroundColor Yellow

# 3) Publicar SEED (si no viene dado)
if ([string]::IsNullOrWhiteSpace($SeedHex)) {
    $seed = (($Turn % 65536) -shl 16) -bor 1  # ejemplo simple
    $SeedHex = "{0:x8}" -f $seed
}
$leaderNode = $nodes | Where-Object { $_.id -eq $leader }
$sigSeed  = Get-PGPSignature $leaderNode.priv $SeedHex
$sigOuter = Get-PGPSignature $leaderNode.priv ("{0}|{1}|{2}" -f $leader, $Turn, $SeedHex)

$body = @{ leaderId=$leader; encryptedSeed=$sigSeed; turn=$Turn; signature=$sigOuter; seedHex=$SeedHex } | ConvertTo-Json
$r = Invoke-RestMethod -Uri "$Api/leader/random-seed" -Method Post -ContentType "application/json" -Body $body
Write-Host ("SEED     {0}: {1}" -f $leader, ($r | ConvertTo-Json -Compress)) -ForegroundColor Green

# 4) VOTOS (todos votan al líder)
foreach ($n in $nodes) {
    $sigVote = Get-PGPSignature $n.priv ("vote|{0}|{1}|{2}" -f $n.id, $leader, $Turn)
    $sigEnv  = Get-PGPSignature $n.priv ("envelope|{0}|{1}" -f $n.id, $Turn)
    $body = @{ nodeId=$n.id; leaderId=$leader; turn=$Turn; encryptedVote=$sigVote; signature=$sigEnv } | ConvertTo-Json
    $r = Invoke-RestMethod -Uri "$Api/consensus/vote" -Method Post -ContentType "application/json" -Body $body
    Write-Host ("VOTE     {0}: {1}" -f $n.id, ($r | ConvertTo-Json -Compress)) -ForegroundColor Green
}

# 5) RESULTADO
$r = Invoke-RestMethod -Uri "$Api/consensus/result" -Method Get
Write-Host ("RESULT: {0}" -f ($r | ConvertTo-Json -Compress)) -ForegroundColor Magenta

# 6) PROPONER BLOQUE (proposer: node_a, ejemplo)
$prop = $nodes | Where-Object { $_.id -eq "node_a" }
$timestamp = [DateTime]::UtcNow.ToString("yyyy-MM-ddTHH:mm:ssZ")
$sigProp = Get-PGPSignature $prop.priv ("{0}|{1}|{2}" -f 1, "abc", $timestamp)
$body = @{
  proposerId = "node_a"
  block      = @{ index=1; timestamp=$timestamp; transactions=@(); previousHash="abc" }
  signature  = $sigProp
} | ConvertTo-Json -Depth 6
$r = Invoke-RestMethod -Uri "$Api/block/propose" -Method Post -ContentType "application/json" -Body $body
Write-Host ("PROPOSE: {0}" -f ($r | ConvertTo-Json -Compress)) -ForegroundColor Cyan

# 7) SUBMIT BLOQUE (líder firma hash)
$sigLead = Get-PGPSignature $leaderNode.priv $BlockHash
$body = @{
  leaderId = $leader
  block    = @{ index=1; timestamp=$timestamp; transactions=@(); previousHash="abc"; hash=$BlockHash }
  signature= $sigLead
} | ConvertTo-Json -Depth 6
$r = Invoke-RestMethod -Uri "$Api/block/submit" -Method Post -ContentType "application/json" -Body $body
Write-Host ("SUBMIT : {0}" -f ($r | ConvertTo-Json -Compress)) -ForegroundColor Cyan

# 8) (Opcional) REPORTE DE LÍDER
if ($DoReport) {
    $sigRep = Get-PGPSignature $prop.priv ("{0}|{1}|{2}|{3}" -f "node_a", $leader, "invalid signature", $BlockHash)
    $body = @{
      reporterId = "node_a"
      leaderId   = $leader
      evidence   = @{ reason="invalid signature"; blockHash=$BlockHash }
      signature  = $sigRep
    } | ConvertTo-Json -Depth 6
    $r = Invoke-RestMethod -Uri "$Api/leader/report" -Method Post -ContentType "application/json" -Body $body
    Write-Host ("REPORT : {0}" -f ($r | ConvertTo-Json -Compress)) -ForegroundColor DarkYellow
}

Write-Host "Demo completada." -ForegroundColor Green
