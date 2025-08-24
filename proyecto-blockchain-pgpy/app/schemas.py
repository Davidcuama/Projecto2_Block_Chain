from pydantic import BaseModel
from typing import List, Any, Optional

class RegisterIn(BaseModel):
    nodeId: str
    ip: str
    publicKeyArmored: str     # PGP public key (ASCII-armored)
    signature: str            # detached signature over "nodeId|ip|publicKeyArmored"

class RegisterOut(BaseModel):
    status: str = "registered"
    assignedOrder: int

class FreezeIn(BaseModel):
    nodeId: str
    tokens: int
    signature: str            # detached signature over "nodeId|tokens"

class FreezeOut(BaseModel):
    status: str = "ok"
    frozenTokens: int

class LeaderSeedIn(BaseModel):
    leaderId: str
    encryptedSeed: str        # detached signature over seedHex
    turn: int
    signature: str            # detached signature over "leaderId|turn|seedHex"
    seedHex: str              # 8 hex chars

class Ack(BaseModel):
    status: str

class VoteIn(BaseModel):
    nodeId: str
    leaderId: str
    turn: int
    encryptedVote: str        # detached signature over "vote|nodeId|leaderId|turn"
    signature: Optional[str] = ""  # detached signature over "envelope|nodeId|turn" (optional)

class ConsensusResult(BaseModel):
    leader: str
    agreement: float
    thresholdReached: bool

class BlockBody(BaseModel):
    index: int
    timestamp: str
    transactions: List[Any]
    previousHash: str
    hash: Optional[str] = None

class BlockProposeIn(BaseModel):
    proposerId: str
    block: BlockBody
    signature: str            # detached signature over "index|previousHash|timestamp"

class BlockSubmitIn(BaseModel):
    leaderId: str
    block: BlockBody
    signature: str            # detached signature over "hash"

class LeaderReportIn(BaseModel):
    reporterId: str
    leaderId: str
    evidence: dict
    signature: str            # detached signature over "reporterId|leaderId|reason|blockHash"
