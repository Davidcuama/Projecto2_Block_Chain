# Proyecto Blockchain + PGPy — Guía de ejecución

##  Índice

1. **Resumen del sistema**
2. **Requisitos**
3. **Estructura de carpetas**
4. **Preparación de llaves PGP**
5. **Levantar la red con Docker**
6. **Comprobaciones básicas**
7. **Flujo completo (registro → seed → votos → resultado → bloque → reporte)**
   - Opción A: con **script cliente** (recomendado)
   - Opción B: **llamadas manuales** con PowerShell
8. **Endpoints principales**
9. **Notas de código / decisiones clave**
10. **Solución de problemas**
11. **Comandos útiles**

---

## 1) Resumen del sistema

- **Backend**: FastAPI (Uvicorn) — API de consenso.
- **Criptografía**: PGP **(PGPy)**. El servidor **verifica** firmas; las firmas se hacen **en el cliente**.
- **Cliente**: script Python que firma con PGP y llama a la API.
- **Infra**: `docker-compose` levanta 3 servicios (node_a/b/c) en una red bridge con IPs fijas.
- **Claves**:
  - **Privadas**: se usan **solo** desde el cliente para firmar requests.
  - **Públicas**: se registran en el backend para verificar firmas.

---

## 2) Requisitos

- Windows 10/11 con **PowerShell**.
- **Docker Desktop** con **Docker Compose**.
- **Python 3.11** (en el host) para ejecutar los scripts de cliente/firmado.
- (Opcional) VS Code / Visual Studio.

---

## 3) Estructura de carpetas esperada

```
proyecto-blockchain-pgpy/
  app/
    main.py
    api/routes.py
    core/crypto_pgpy.py
    core/consensus.py
    core/models.py
    schemas.py
  scripts/
    client_pgp_demo.py
    sign_text.py
    demo_flow.ps1
  keys/
    node_a_priv.asc
    node_a_pub.asc
    node_b_priv.asc
    node_b_pub.asc
    node_c_priv.asc
    node_c_pub.asc
  docker-compose.yml
  requirements.txt
  README.md
```

> Sugerencia: evita el Escritorio por permisos. Usa por ejemplo `C:\dev\proyecto-blockchain-pgpy\`.

---

## 4) Preparación de llaves PGP

1) Crea la carpeta `keys/` (si no existe).  
2) Coloca **seis archivos**:
   - Privadas: `node_a_priv.asc`, `node_b_priv.asc`, `node_c_priv.asc`  
   - Públicas: `node_a_pub.asc`, `node_b_pub.asc`, `node_c_pub.asc`

> Deben ser ASCII-armored (`-----BEGIN ... -----`). No se requiere GPG en tiempo de ejecución.

---

## 5) Levantar la red con Docker

Desde la raíz del proyecto:

```powershell
docker compose build
docker compose up -d
```

Puertos por defecto en el host:
- **node_a** → http://127.0.0.1:8001
- **node_b** → http://127.0.0.1:8002
- **node_c** → http://127.0.0.1:8003

Abrir Swagger de `node_a`: http://127.0.0.1:8001/docs

---

## 6) Comprobaciones básicas

```powershell
# Ver estado
docker compose ps

# Logs de node_a
docker logs -f node_a

# Probar API desde dentro del contenedor
docker exec -it node_a python -c "import requests;print(requests.get('http://127.0.0.1:8000/docs').status_code)"
```

Debes ver **200** y en logs: `Uvicorn running on http://0.0.0.0:8000`.

---

## 7) Flujo completo

### Suposiciones
- Coordenamos todas las llamadas contra **node_a**: `http://127.0.0.1:8001`.
- IPs:
  - node_a → 172.28.0.11
  - node_b → 172.28.0.12
  - node_c → 172.28.0.13
- Rotación por IP descendente → orden: **node_c**, **node_b**, **node_a**
  - Turno 0 → líder: node_c
  - Turno 1 → líder: node_b
  - Turno 2 → líder: node_a

### Opción A: con script cliente (recomendado)

`scripts/client_pgp_demo.py` (incluido en el repo) registra, congela tokens, vota y puede publicar el **seed** cuando el nodo ejecutor es líder de rotación.

**Ejemplos (`turn=0`):**
```powershell
# Registrar + congelar + votar (cada nodo contra node_a)
python scripts\client_pgp_demo.py --api http://127.0.0.1:8001 --node-id node_a --node-ip 172.28.0.11 --priv keys\node_a_priv.asc --pub keys\node_a_pub.asc --turn 0
python scripts\client_pgp_demo.py --api http://127.0.0.1:8001 --node-id node_b --node-ip 172.28.0.12 --priv keys\node_b_priv.asc --pub keys\node_b_pub.asc --turn 0
python scripts\client_pgp_demo.py --api http://127.0.0.1:8001 --node-id node_c --node-ip 172.28.0.13 --priv keys\node_c_priv.asc --pub keys\node_c_pub.asc --turn 0

# Publicar seed del turno 0 (líder = node_c)
python scripts\client_pgp_demo.py --api http://127.0.0.1:8001 --node-id node_c --node-ip 172.28.0.13 --priv keys\node_c_priv.asc --pub keys\node_c_pub.asc --turn 0 --seed-leader

# Ver resultado
curl http://127.0.0.1:8001/consensus/result
```

## Opción B: llamadas manuales con PowerShell

Esta opción te permite “ir a mano” endpoint por endpoint usando **PowerShell** en Windows.  
Las **firmas PGP** se generan localmente con `scripts/sign_text.py` (PGPy) y luego se envían con `Invoke-RestMethod`.

> **Prerequisitos**
> - La API debe estar corriendo (p. ej. `node_a` en `http://127.0.0.1:8001`).
> - Tener las 6 llaves en `./keys/`: `node_a_priv.asc / node_a_pub.asc / node_b_priv.asc / node_b_pub.asc / node_c_priv.asc / node_c_pub.asc`.
> - `scripts/sign_text.py` presente (ver anexo del README).
> - `pip install -r requirements.txt` en tu host para tener `pgpy` y `requests`.

### 0) Helpers (pégalos 1 sola vez por sesión)

```powershell
# API objetivo (coordinador)
$API = "http://127.0.0.1:8001"

# Lee archivos como UN string completo (evita arrays/objetos)
function Get-FileText {
    param([string]$Path)
    [System.IO.File]::ReadAllText((Resolve-Path $Path), [System.Text.Encoding]::UTF8)
}

# Firma PGP (une líneas devueltas por Python en un único string)
function Get-PGPSignature {
    param([string]$PrivPath, [string]$TextToSign)
    [string]::Join("`n", (python scripts\sign_text.py $PrivPath $TextToSign))
}

# Utilidad para calcular el líder por rotación (IP descendente)
function IpToInt([string]$ip) {
    $p = $ip.Split('.').ForEach([int])
    ($p[0] -shl 24) -bor ($p[1] -shl 16) -bor ($p[2] -shl 8) -bor $p[3]
}
```
-1 Registrar nodos
```
Texto a firmar: nodeId|ip|publicKeyArmored (la pública completa, ASCII-armored).

node_a

$pubA     = Get-FileText ".\keys\node_a_pub.asc"
$payloadA = ("node_a|172.28.0.11|{0}" -f $pubA)
$sigRegA  = Get-PGPSignature "keys\node_a_priv.asc" $payloadA

$body = @{
  nodeId           = "node_a"
  ip               = "172.28.0.11"
  publicKeyArmored = $pubA
  signature        = $sigRegA
} | ConvertTo-Json -Depth 6

Invoke-RestMethod -Uri "$API/network/register" -Method Post -ContentType "application/json" -Body $body


node_b

$pubB     = Get-FileText ".\keys\node_b_pub.asc"
$payloadB = ("node_b|172.28.0.12|{0}" -f $pubB)
$sigRegB  = Get-PGPSignature "keys\node_b_priv.asc" $payloadB

$body = @{ nodeId="node_b"; ip="172.28.0.12"; publicKeyArmored=$pubB; signature=$sigRegB } | ConvertTo-Json -Depth 6
Invoke-RestMethod -Uri "$API/network/register" -Method Post -ContentType "application/json" -Body $body


node_c

$pubC     = Get-FileText ".\keys\node_c_pub.asc"
$payloadC = ("node_c|172.28.0.13|{0}" -f $pubC)
$sigRegC  = Get-PGPSignature "keys\node_c_priv.asc" $payloadC

$body = @{ nodeId="node_c"; ip="172.28.0.13"; publicKeyArmored=$pubC; signature=$sigRegC } | ConvertTo-Json -Depth 6
Invoke-RestMethod -Uri "$API/network/register" -Method Post -ContentType "application/json" -Body $body
```
-2 Congelar tokens
```
Texto a firmar: nodeId|tokens

# node_a
$sigFrA = Get-PGPSignature "keys\node_a_priv.asc" "node_a|100"
Invoke-RestMethod -Uri "$API/tokens/freeze" -Method Post -ContentType "application/json" -Body (@{nodeId="node_a";tokens=100;signature=$sigFrA} | ConvertTo-Json)

# node_b
$sigFrB = Get-PGPSignature "keys\node_b_priv.asc" "node_b|100"
Invoke-RestMethod -Uri "$API/tokens/freeze" -Method Post -ContentType "application/json" -Body (@{nodeId="node_b";tokens=100;signature=$sigFrB} | ConvertTo-Json)

# node_c
$sigFrC = Get-PGPSignature "keys\node_c_priv.asc" "node_c|100"
Invoke-RestMethod -Uri "$API/tokens/freeze" -Method Post -ContentType "application/json" -Body (@{nodeId="node_c";tokens=100;signature=$sigFrC} | ConvertTo-Json)
```
-3 Publicar seed (líder del turno)
```
Con IPs 172.28.0.11/12/13, la rotación por IP descendente es: node_c > node_b > node_a.
Ejemplo turno 0 → líder = node_c.

Firmas:

encryptedSeed = firma sobre seedHex

signature (outer) = firma sobre "leaderId|turn|seedHex"

$turn = 0
$seedHex  = "00010001"   # 8 hex (32 bits)
$sigSeed  = Get-PGPSignature "keys\node_c_priv.asc" $seedHex
$sigOuter = Get-PGPSignature "keys\node_c_priv.asc" ("node_c|{0}|{1}" -f $turn,$seedHex)

$body = @{
  leaderId      = "node_c"
  encryptedSeed = $sigSeed
  turn          = $turn
  signature     = $sigOuter
  seedHex       = $seedHex
} | ConvertTo-Json

Invoke-RestMethod -Uri "$API/leader/random-seed" -Method Post -ContentType "application/json" -Body $body


Calcular líder por rotación (opcional):

$nodes = @(
  @{ id="node_a"; ip="172.28.0.11" },
  @{ id="node_b"; ip="172.28.0.12" },
  @{ id="node_c"; ip="172.28.0.13" }
)
$sorted = $nodes | Sort-Object @{Expression={ IpToInt $_.ip }} -Descending
$leader = $sorted[ $turn % $sorted.Count ].id
$leader
```
-4 Votar (los 3 nodos)
```
Firmas:

encryptedVote = "vote|nodeId|leaderId|turn"

signature (sobre) = "envelope|nodeId|turn"

# node_a → node_c (turno 0)
$sigVote = Get-PGPSignature "keys\node_a_priv.asc" "vote|node_a|node_c|0"
$sigEnv  = Get-PGPSignature "keys\node_a_priv.asc" "envelope|node_a|0"
Invoke-RestMethod -Uri "$API/consensus/vote" -Method Post -ContentType "application/json" `
  -Body (@{ nodeId="node_a"; leaderId="node_c"; turn=0; encryptedVote=$sigVote; signature=$sigEnv } | ConvertTo-Json)

# node_b → node_c
$sigVote = Get-PGPSignature "keys\node_b_priv.asc" "vote|node_b|node_c|0"
$sigEnv  = Get-PGPSignature "keys\node_b_priv.asc" "envelope|node_b|0"
Invoke-RestMethod -Uri "$API/consensus/vote" -Method Post -ContentType "application/json" `
  -Body (@{ nodeId="node_b"; leaderId="node_c"; turn=0; encryptedVote=$sigVote; signature=$sigEnv } | ConvertTo-Json)

# node_c → node_c
$sigVote = Get-PGPSignature "keys\node_c_priv.asc" "vote|node_c|node_c|0"
$sigEnv  = Get-PGPSignature "keys\node_c_priv.asc" "envelope|node_c|0"
Invoke-RestMethod -Uri "$API/consensus/vote" -Method Post -ContentType "application/json" `
  -Body (@{ nodeId="node_c"; leaderId="node_c"; turn=0; encryptedVote=$sigVote; signature=$sigEnv } | ConvertTo-Json)
```
-5 Ver resultado
```
Invoke-RestMethod -Uri "$API/consensus/result" -Method Get
# Esperado: leader="node_c", agreement≈0.6667, thresholdReached=true
```
-6 Proponer bloque (proposer firma)
```
Texto a firmar: index|previousHash|timestamp
(Ejemplo: proposer = node_a)

$SIG_PROP = Get-PGPSignature "keys\node_a_priv.asc" "1|abc|2025-08-24T12:00:00Z"

$body = @{
  proposerId = "node_a"
  block      = @{
    index        = 1
    timestamp    = "2025-08-24T12:00:00Z"
    transactions = @()
    previousHash = "abc"
  }
  signature = $SIG_PROP
} | ConvertTo-Json -Depth 6

Invoke-RestMethod -Uri "$API/block/propose" -Method Post -ContentType "application/json" -Body $body
```
-7 Enviar bloque (líder firma hash)
```
Texto a firmar: hash (solo el hash del bloque).
(Ejemplo: líder del turno 0 = node_c)

$SIG_LEAD = Get-PGPSignature "keys\node_c_priv.asc" "abcd1234"

$body = @{
  leaderId = "node_c"
  block    = @{
    index        = 1
    timestamp    = "2025-08-24T12:00:00Z"
    transactions = @()
    previousHash = "abc"
    hash         = "abcd1234"
  }
  signature = $SIG_LEAD
} | ConvertTo-Json -Depth 6

Invoke-RestMethod -Uri "$API/block/submit" -Method Post -ContentType "application/json" -Body $body
```
-8 líder fraudoliento (opcional)
```
Texto a firmar: reporterId|leaderId|reason|blockHash
(Ejemplo: node_a reporta a node_c)

$SIG_REP = Get-PGPSignature "keys\node_a_priv.asc" "node_a|node_c|invalid signature|abcd1234"

$body = @{
  reporterId = "node_a"
  leaderId   = "node_c"
  evidence   = @{ reason="invalid signature"; blockHash="abcd1234" }
  signature  = $SIG_REP
} | ConvertTo-Json -Depth 6

Invoke-RestMethod -Uri "$API/leader/report" -Method Post -ContentType "application/json" -Body $body
# Cuando reporten ≥ 2/3, el estado será "expelled"
---
```
-9 Siguiente turno (ejemplo: turno 1)
```
Con estas IPs, el líder será node_b.
Repite seed y votos cambiando turn=1 y leaderId="node_b".

$turn = 1
$seedHex  = "00010002"
$sigSeed  = Get-PGPSignature "keys\node_b_priv.asc" $seedHex
$sigOuter = Get-PGPSignature "keys\node_b_priv.asc" ("node_b|{0}|{1}" -f $turn,$seedHex)

$body = @{ leaderId="node_b"; encryptedSeed=$sigSeed; turn=$turn; signature=$sigOuter; seedHex=$seedHex } | ConvertTo-Json
Invoke-RestMethod -Uri "$API/leader/random-seed" -Method Post -ContentType "application/json" -Body $body

---
```

Tips de troubleshooting rápidos
```
“Input should be a valid string” (publicKeyArmored / signature)
Asegúrate de que no estás enviando arrays u objetos:

Lee archivos con Get-FileText (no Get-Content sin -Raw).

Usa Get-PGPSignature (hace -join de líneas).

Revisa tipos:

$pubA.GetType().FullName    # System.String
$sigRegA.GetType().FullName # System.String


“unknown turn (seed not set)” → publica el seed del turno antes de votar.

No abre /docs → usa http://127.0.0.1:8001/docs (o cambia puertos en docker-compose.yml y recrea con --force-recreate).
```
## 8) Endpoints principales

- `POST /network/register` — Firma: `"nodeId|ip|publicKeyArmored"`  
- `POST /tokens/freeze` — Firma: `"nodeId|tokens"`  
- `POST /leader/random-seed` — `encryptedSeed`: firma sobre `seedHex`; `signature`: firma sobre `"leaderId|turn|seedHex"`  
- `POST /consensus/vote` — `encryptedVote`: firma sobre `"vote|nodeId|leaderId|turn"`; `signature` (opcional): `"envelope|nodeId|turn"`  
- `GET /consensus/result`  
- `POST /block/propose` — Firma: `"index|previousHash|timestamp"`  
- `POST /block/submit` — Firma: `hash`  
- `POST /leader/report` — Firma: `"reporterId|leaderId|reason|blockHash"`

---

## 9) Notas de código / decisiones clave

- **Imports corregidos**: `app/api/routes.py` usa imports **absolutos** (`from schemas import ...`, `from core...`).
- **Modelos**: `Block.previousHash` en `core/models.py` está en **camelCase** para alinear con Pydantic.
- **Privadas en servidor**: la API **no firma**; solo **verifica** con la **pública**. Las firmas se hacen en el **cliente**.

---

## 10) Solución de problemas

- No abre `http://localhost:8001/docs` → usa `http://127.0.0.1:8001/docs` o cambia puertos de publish en `docker-compose.yml` y recrea.
- `container ... is not running` / ImportError → usa la versión de código con imports absolutos; mira logs con `docker logs -f node_a`.
- “Input should be a valid string” en `publicKeyArmored`/`signature` → asegúrate de enviar **strings**, no arrays/objetos. En PowerShell usa `Get-FileText` y `Get-PGPSignature`.
- “unknown turn (seed not set)” al votar → publica el **seed** del turno antes de votar.

---

## 11) Comandos útiles

```powershell
docker compose ps -a
docker logs -f node_a
docker exec -it node_a sh
docker exec -it node_a python -c "import requests; print(requests.get('http://127.0.0.1:8000/docs').status_code)"
docker compose build
docker compose up -d --force-recreate
curl http://127.0.0.1:8001/consensus/result
```

---

## Anexo: Helper de firmas `scripts/sign_text.py`

```python
#!/usr/bin/env python3
import sys
from pgpy import PGPKey
if len(sys.argv) < 3:
    print("Usage: python scripts/sign_text.py <priv.asc> <text-to-sign>")
    sys.exit(1)
priv_path, text = sys.argv[1], sys.argv[2]
key, _ = PGPKey.from_file(priv_path)
if key.is_protected:
    print("ERROR: key has passphrase (demo script doesn't unlock).")
    sys.exit(2)
sig = key.sign(text, detached=True)
print(str(sig))
```
