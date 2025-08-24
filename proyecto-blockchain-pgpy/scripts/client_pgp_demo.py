#!/usr/bin/env python3
import argparse, requests
from pgpy import PGPKey

def load_priv(path):
    key, _ = PGPKey.from_file(path)
    return key

def load_pub_text(path):
    return open(path, "r", encoding="utf-8").read()

def sign_detached(priv, text: str) -> str:
    if priv.is_protected:
        raise RuntimeError("La llave privada tiene passphrase; usa una sin passphrase o implementa unlock().")
    sig = priv.sign(text, detached=True)
    return str(sig)

def parse_nodes_ip(s: str):
    # "node_a=172.28.0.11,node_b=172.28.0.12,node_c=172.28.0.13"
    pairs = [x.strip() for x in s.split(",") if x.strip()]
    out = {}
    for p in pairs:
        k, v = [t.strip() for t in p.split("=")]
        out[k] = v
    return out

def ip_to_int(ip):
    a,b,c,d = map(int, ip.split("."))
    return (a<<24)|(b<<16)|(c<<8)|d

def rotation_leader(nodes_ip: dict, turn: int) -> str:
    order = sorted(nodes_ip.items(), key=lambda kv: ip_to_int(kv[1]), reverse=True)
    return order[turn % len(order)][0]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", required=True)            # ej. http://127.0.0.1:8001
    ap.add_argument("--node-id", required=True)
    ap.add_argument("--node-ip", required=True)
    ap.add_argument("--priv", required=True)
    ap.add_argument("--pub", required=True)
    ap.add_argument("--turn", type=int, required=True)
    ap.add_argument("--nodes-ip", default="node_a=172.28.0.11,node_b=172.28.0.12,node_c=172.28.0.13")
    ap.add_argument("--seed-leader", action="store_true")
    ap.add_argument("--tokens", type=int, default=100)
    args = ap.parse_args()

    priv = load_priv(args.priv)
    publicKeyArmored = load_pub_text(args.pub)

    # REGISTER
    reg_payload = f"{args.node_id}|{args.node_ip}|{publicKeyArmored}"
    reg_sig = sign_detached(priv, reg_payload)
    r = requests.post(f"{args.api}/network/register", json={
        "nodeId": args.node_id, "ip": args.node_ip,
        "publicKeyArmored": publicKeyArmored, "signature": reg_sig
    })
    print("REGISTER", r.status_code, r.text)

    # FREEZE
    fr_payload = f"{args.node_id}|{args.tokens}"
    fr_sig = sign_detached(priv, fr_payload)
    r = requests.post(f"{args.api}/tokens/freeze", json={
        "nodeId": args.node_id, "tokens": args.tokens, "signature": fr_sig
    })
    print("FREEZE", r.status_code, r.text)

    # SEED (si corresponde)
    nodes_ip = parse_nodes_ip(args.nodes_ip)
    rl = rotation_leader(nodes_ip, args.turn)
    if args.seed_leader:
        if args.node_id != rl:
            print(f"[WARN] --seed-leader pedido pero {args.node_id} no es rotation leader ({rl}) en turn {args.turn}")
        seed = ((args.turn % 65536) << 16) | 1  # ejemplo simple
        seedHex = f"{seed:08x}"
        sig_seed = sign_detached(priv, seedHex)
        outer = sign_detached(priv, f"{args.node_id}|{args.turn}|{seedHex}")
        r = requests.post(f"{args.api}/leader/random-seed", json={
            "leaderId": args.node_id, "encryptedSeed": sig_seed, "turn": args.turn,
            "signature": outer, "seedHex": seedHex
        })
        print("SEED", r.status_code, r.text)

    # VOTE (todos votan al rotation leader)
    leaderId = rl
    vote_msg = f"vote|{args.node_id}|{leaderId}|{args.turn}"
    v_sig = sign_detached(priv, vote_msg)
    env = sign_detached(priv, f"envelope|{args.node_id}|{args.turn}")
    r = requests.post(f"{args.api}/consensus/vote", json={
        "nodeId": args.node_id, "leaderId": leaderId, "turn": args.turn,
        "encryptedVote": v_sig, "signature": env
    })
    print("VOTE", r.status_code, r.text)

    # RESULT
    r = requests.get(f"{args.api}/consensus/result")
    print("RESULT", r.status_code, r.text)

if __name__ == "__main__":
    main()
