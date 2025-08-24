from fastapi import APIRouter, HTTPException
from schemas import (
    RegisterIn, RegisterOut, FreezeIn, FreezeOut, LeaderSeedIn, Ack,
    VoteIn, ConsensusResult, BlockProposeIn, BlockSubmitIn, LeaderReportIn
)
from core.models import DB, Node, Block
from core.crypto_pgpy import load_pub_from_armored, verify_detached
from core import consensus

router = APIRouter()

@router.post("/network/register", response_model=RegisterOut)
def register(body: RegisterIn):
    # Verifica firma PGP (detached) sobre "nodeId|ip|publicKeyArmored"
    payload = f"{body.nodeId}|{body.ip}|{body.publicKeyArmored}"
    pub = load_pub_from_armored(body.publicKeyArmored)
    if not verify_detached(pub, payload, body.signature):
        raise HTTPException(400, "invalid signature")
    nodes_ip = {**{nid: n.ip for nid, n in DB.nodes.items()}, body.nodeId: body.ip}
    order = consensus.leader_rotation_order(nodes_ip)
    assigned = order.index(body.nodeId)
    DB.nodes[body.nodeId] = Node(body.nodeId, body.ip, body.publicKeyArmored, assigned)
    return RegisterOut(assignedOrder=assigned)

@router.post("/tokens/freeze", response_model=FreezeOut)
def freeze(body: FreezeIn):
    node = DB.nodes.get(body.nodeId)
    if not node:
        raise HTTPException(404, "node not registered")
    payload = f"{body.nodeId}|{body.tokens}"
    pub = load_pub_from_armored(node.public_key_armored)
    if not verify_detached(pub, payload, body.signature):
        raise HTTPException(400, "invalid signature")
    DB.frozen_tokens[body.nodeId] = int(body.tokens)
    return FreezeOut(frozenTokens=int(body.tokens))

@router.post("/leader/random-seed", response_model=Ack)
def leader_seed(body: LeaderSeedIn):
    leader = DB.nodes.get(body.leaderId)
    if not leader:
        raise HTTPException(404, "leader not registered")
    rotation_leader = consensus.rotation_leader_for_turn({nid: n.ip for nid, n in DB.nodes.items()}, body.turn)
    if rotation_leader != body.leaderId:
        raise HTTPException(403, f"not rotation leader for turn {body.turn}")
    # Validar seedHex (8 hex chars -> 32 bits)
    try:
        seed_int = int(body.seedHex, 16)
    except Exception:
        raise HTTPException(400, "invalid seedHex")
    if len(body.seedHex) != 8:
        raise HTTPException(400, "seedHex must be 8 hex chars")
    # encryptedSeed = firma PGP detached sobre seedHex
    pub = load_pub_from_armored(leader.public_key_armored)
    if not verify_detached(pub, body.seedHex, body.encryptedSeed):
        raise HTTPException(400, "invalid encryptedSeed signature")
    # Firma envolvente: "leaderId|turn|seedHex"
    outer = f"{body.leaderId}|{body.turn}|{body.seedHex}"
    if not verify_detached(pub, outer, body.signature):
        raise HTTPException(400, "invalid outer signature")
    DB.leader_seeds[body.turn] = seed_int
    return Ack(status="received")

@router.post("/consensus/vote", response_model=Ack)
def vote(body: VoteIn):
    node = DB.nodes.get(body.nodeId)
    if not node:
        raise HTTPException(404, "node not registered")
    if body.turn not in DB.leader_seeds:
        raise HTTPException(400, "unknown turn (seed not set)")
    # Firma PGP detached sobre "vote|nodeId|leaderId|turn"
    msg = f"vote|{body.nodeId}|{body.leaderId}|{body.turn}"
    pub = load_pub_from_armored(node.public_key_armored)
    if not verify_detached(pub, msg, body.encryptedVote):
        raise HTTPException(400, "invalid vote signature")
    # Firma opcional del sobre: "envelope|nodeId|turn"
    if body.signature:
        env = f"envelope|{body.nodeId}|{body.turn}"
        if not verify_detached(pub, env, body.signature):
            raise HTTPException(400, "invalid envelope signature")
    DB.votes.setdefault(body.turn, {})[body.nodeId] = body.leaderId
    return Ack(status="recorded")

@router.get("/consensus/result", response_model=ConsensusResult)
def result():
    if not DB.leader_seeds:
        raise HTTPException(404, "no consensus rounds yet")
    turn = max(DB.leader_seeds.keys())
    vote_map = DB.votes.get(turn, {})
    if not vote_map:
        return ConsensusResult(leader="", agreement=0.0, thresholdReached=False)
    from collections import Counter
    c = Counter(vote_map.values())
    leader, cnt = c.most_common(1)[0]
    agreement, ok = consensus.two_thirds_threshold(cnt, len(DB.nodes))
    return ConsensusResult(leader=leader, agreement=agreement, thresholdReached=ok)

@router.post("/block/propose", response_model=Ack)
def propose(body: BlockProposeIn):
    prop = DB.nodes.get(body.proposerId)
    if not prop:
        raise HTTPException(404, "proposer not registered")
    # Firma PGP detached sobre "index|previousHash|timestamp"
    payload = f"{body.block.index}|{body.block.previousHash}|{body.block.timestamp}"
    pub = load_pub_from_armored(prop.public_key_armored)
    if not verify_detached(pub, payload, body.signature):
        raise HTTPException(400, "invalid signature")
    DB.pending_blocks[body.block.index] = Block(**body.block.model_dump())
    return Ack(status="pending consensus")

@router.post("/block/submit", response_model=Ack)
def submit(body: BlockSubmitIn):
    lead = DB.nodes.get(body.leaderId)
    if not lead:
        raise HTTPException(404, "leader not registered")
    if not body.block.hash:
        raise HTTPException(400, "missing block.hash")
    # Firma PGP detached sobre el hash
    payload = body.block.hash
    pub = load_pub_from_armored(lead.public_key_armored)
    if not verify_detached(pub, payload, body.signature):
        raise HTTPException(400, "invalid signature")
    return Ack(status="broadcasted")

@router.post("/leader/report", response_model=Ack)
def report(body: LeaderReportIn):
    reporter = DB.nodes.get(body.reporterId)
    leader = DB.nodes.get(body.leaderId)
    if not reporter or not leader:
        raise HTTPException(404, "unknown reporter/leader")
    reason = str(body.evidence.get("reason"))
    bh = str(body.evidence.get("blockHash"))
    payload = f"{body.reporterId}|{body.leaderId}|{reason}|{bh}"
    pub = load_pub_from_armored(reporter.public_key_armored)
    if not verify_detached(pub, payload, body.signature):
        raise HTTPException(400, "invalid signature")
    DB.reports.setdefault(body.leaderId, set()).add(body.reporterId)
    count = len(DB.reports[body.leaderId])
    _, ok = consensus.two_thirds_threshold(count, len(DB.nodes))
    if ok:
        DB.expelled.add(body.leaderId)
        return Ack(status="expelled")
    return Ack(status="under review")
