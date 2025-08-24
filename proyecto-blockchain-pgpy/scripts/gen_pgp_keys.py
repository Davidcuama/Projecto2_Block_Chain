#!/usr/bin/env python3
from pgpy import PGPKey, PGPUID
from pgpy.constants import PubKeyAlgorithm, KeyFlags, HashAlgorithm, SymmetricKeyAlgorithm, CompressionAlgorithm
import os, sys, pathlib

def ensure_dir(path):
    pathlib.Path(path).mkdir(parents=True, exist_ok=True)

def write_text_safe(path, txt):
    try:
        ensure_dir(os.path.dirname(path))
        with open(path, "w", encoding="utf-8") as f:
            f.write(txt)
        return path
    except PermissionError:
        # Carpeta alternativa segura en LOCALAPPDATA (no suele estar protegida por OneDrive/Defender)
        alt_dir = os.path.join(os.environ.get("LOCALAPPDATA", os.getcwd()), "proyecto-blockchain-pgpy", "keys")
        ensure_dir(alt_dir)
        alt = os.path.join(alt_dir, os.path.basename(path))
        with open(alt, "w", encoding="utf-8") as f:
            f.write(txt)
        print(f"[WARN] Sin permisos en {path}. Guardado en {alt}.")
        return alt

def gen(node_id: str):
    key = PGPKey.new(PubKeyAlgorithm.RSAEncryptOrSign, 2048)
    uid = PGPUID.new(node_id)
    key.add_uid(uid,
                usage={KeyFlags.Sign, KeyFlags.EncryptCommunications},
                hashes=[HashAlgorithm.SHA256],
                ciphers=[SymmetricKeyAlgorithm.AES256],
                compression=[CompressionAlgorithm.ZLIB])

    priv_path = write_text_safe(os.path.join("keys", f"{node_id}_priv.asc"), str(key))
    pub_path  = write_text_safe(os.path.join("keys", f"{node_id}_pub.asc"),  str(key.pubkey))
    print(f"OK: {priv_path} / {pub_path}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/gen_pgp_keys.py <node_id>")
        raise SystemExit(1)
    gen(sys.argv[1])
