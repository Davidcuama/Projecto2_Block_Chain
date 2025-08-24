from typing import Optional
from pgpy import PGPKey, PGPMessage, PGPSignature

def load_pub_from_armored(armored: str) -> PGPKey:
    key, _ = PGPKey.from_blob(armored)
    return key

def load_priv_from_file(path: str, passphrase: Optional[str] = None) -> PGPKey:
    key, _ = PGPKey.from_file(path)
    if key.is_protected and passphrase is not None:
        key.unlock(passphrase)
    return key

def sign_detached(priv: PGPKey, text: str) -> str:
    # Detached signature over utf-8 text
    sig = priv.sign(text, detached=True)
    return str(sig)

def verify_detached(pub: PGPKey, text: str, sig_armored: str) -> bool:
    try:
        sig = PGPSignature.from_blob(sig_armored)
        return pub.verify(text, sig)
    except Exception:
        return False

def encrypt_text(pub: PGPKey, text: str) -> str:
    msg = PGPMessage.new(text)
    enc = pub.encrypt(msg)
    return str(enc)

def decrypt_text(priv: PGPKey, armored_message: str, passphrase: Optional[str] = None) -> str:
    if priv.is_protected and passphrase is not None:
        priv.unlock(passphrase)
    msg = PGPMessage.from_blob(armored_message)
    dec = priv.decrypt(msg)
    return dec.message
