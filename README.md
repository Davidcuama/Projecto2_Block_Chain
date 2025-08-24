# Proyecto Blockchain + PGPy — Guía de ejecución

## 🧭 Índice

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

### Opción B: llamadas manuales con PowerShell

Para firmas manuales, usa el helper `scripts/sign_text.py` (ver más abajo) y los bloques PowerShell del README original.  
Si prefieres automatizar **todo**, utiliza el script **`scripts/demo_flow.ps1`** incluido en este paquete (ver siguiente sección).

---

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
