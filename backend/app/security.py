import hashlib, secrets, time, os
from fastapi import Request, HTTPException, Depends
from .db import Session, User, LoginSession, Audit


def hash_password(password, salt=None):
    salt = salt or secrets.token_hex(16)
    return (
        salt
        + ":"
        + hashlib.scrypt(
            password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1
        ).hex()
    )


def verify(password, stored):
    return secrets.compare_digest(hash_password(password, stored.split(":")[0]), stored)


def current(request: Request):
    token = request.cookies.get("gridmind", "")
    with Session() as db:
        s = db.get(LoginSession, hashlib.sha256(token.encode()).hexdigest())
        if not s or s.expires < time.time():
            raise HTTPException(401, "Please sign in")
        return db.get(User, s.user_id)


def editor(user=Depends(current)):
    if user.role not in ("admin", "analyst"):
        raise HTTPException(403, "Analyst or admin required")
    return user


def admin(user=Depends(current)):
    if user.role != "admin":
        raise HTTPException(403, "Admin required")
    return user


def audit(user_id, action):
    with Session() as db:
        db.add(Audit(user_id=user_id, action=action))
        db.commit()
