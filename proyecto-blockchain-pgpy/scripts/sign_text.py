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
