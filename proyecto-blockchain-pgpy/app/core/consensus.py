import ipaddress, random
from typing import Dict, List, Tuple

def ip_to_int(ip: str) -> int:
    return int(ipaddress.IPv4Address(ip))

def leader_rotation_order(nodes_ip: Dict[str, str]) -> List[str]:
    # Orden por IP (32-bit) descendente
    return [nid for nid, _ in sorted(nodes_ip.items(), key=lambda kv: ip_to_int(kv[1]), reverse=True)]

def rotation_leader_for_turn(nodes_ip: Dict[str, str], turn: int) -> str:
    order = leader_rotation_order(nodes_ip)
    if not order:
        return ""
    return order[turn % len(order)]

def build_seed(turn: int, rng: random.Random) -> int:
    # 2 bytes = turno, 2 bytes = aleatorio
    high = turn % 65536
    low = rng.randrange(0, 65536)
    return (high << 16) | low

def two_thirds_threshold(count_agree: int, total: int) -> Tuple[float, bool]:
    if total == 0:
        return 0.0, False
    agreement = count_agree / total
    return agreement, agreement >= (2/3)
