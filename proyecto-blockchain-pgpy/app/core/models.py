from dataclasses import dataclass
from typing import Dict, Set

@dataclass
class Node:
    node_id: str
    ip: str
    public_key_armored: str  # ASCII-armored PGP public key
    assigned_order: int

@dataclass
class Block:
    index: int
    timestamp: str
    transactions: list
    previousHash: str   # <-- camelCase para coincidir con el esquema Pydantic
    hash: str | None = None

class InMemoryStore:
    def __init__(self):
        self.nodes: Dict[str, Node] = {}
        self.frozen_tokens: Dict[str, int] = {}
        self.leader_seeds: Dict[int, int] = {}
        self.votes: Dict[int, Dict[str, str]] = {}
        self.pending_blocks: Dict[int, Block] = {}
        self.reports: Dict[str, Set[str]] = {}
        self.expelled: Set[str] = set()

DB = InMemoryStore()
