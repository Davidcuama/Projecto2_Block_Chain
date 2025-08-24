#!/usr/bin/env python3
import sys
from pgpy import PGPKey

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/print_pub.py keys/<node>_pub.asc")
        raise SystemExit(1)
    key, _ = PGPKey.from_file(sys.argv[1])
    print(str(key))
