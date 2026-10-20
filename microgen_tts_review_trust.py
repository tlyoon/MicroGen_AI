"""Role-separated HMAC authenticity for external MicroGen reviewer receipts.

A receipt with 'approved': true is never authorization by itself. Secrets are
held outside lesson folders and source control by the independent reviewer
service; a release audit sees only the explicit trusted keys passed to it.
"""
from __future__ import annotations
import hashlib
import hmac
import json

class TrustError(ValueError):
    pass

ROLES=frozenset({"listening","academic","figures","highlights"})

def _canonical(receipt:dict)->bytes:
    return json.dumps({k:v for k,v in receipt.items() if k!="signature"},
                      sort_keys=True,separators=(",",":"),ensure_ascii=False
                      ).encode("utf-8")

def sign_review_receipt(payload:dict,secret:bytes,role:str)->dict:
    """Review-authority utility; never call from an automatic QA pass."""
    if role not in ROLES or len(secret)<32:
        raise TrustError("Untrusted reviewer role or weak key")
    if payload.get("role")!=role or payload.get("approved") is not True:
        raise TrustError("Receipt must declare its approved reviewer role")
    if not isinstance(payload.get("reviewer"),str) or not payload["reviewer"].strip():
        raise TrustError("Named reviewer required")
    if not payload.get("key_id"):
        raise TrustError("Missing reviewer key ID")
    if not payload.get("reviewed_at"):
        raise TrustError("Dated reviewer attestation required")
    receipt={k:v for k,v in payload.items() if k!="signature"}
    receipt["signature"]=hmac.new(secret,_canonical(receipt),hashlib.sha256).hexdigest()
    return receipt

def verify_review_receipt(receipt:dict|None,role:str,trust:dict|None)->bool:
    if not isinstance(receipt,dict) or role not in ROLES or not isinstance(trust,dict):
        return False
    if receipt.get("role")!=role or receipt.get("approved") is not True:
        return False
    if not isinstance(receipt.get("reviewer"),str) or not receipt["reviewer"].strip():
        return False
    if not receipt.get("reviewed_at") or not isinstance(receipt.get("key_id"),str):
        return False
    key=trust.get(role,{}).get(receipt["key_id"]) if isinstance(trust.get(role),dict) else None
    if not isinstance(key,bytes) or len(key)<32:
        return False
    signature=receipt.get("signature")
    if not isinstance(signature,str) or len(signature)!=64:
        return False
    expected=hmac.new(key,_canonical(receipt),hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected,signature.lower())
