import hmac
from fastapi import Request, Response, HTTPException
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from .config import settings
from contextvars import ContextVar
from uuid import UUID

current_owner = ContextVar("current_owner", default=None)

serializer = URLSafeTimedSerializer(settings.session_secret, salt="admin-session")
COOKIE = "booking_admin"

def valid_credentials(username: str, password: str) -> bool:
    return bool(settings.admin_username and settings.admin_password) and hmac.compare_digest(username.encode(), settings.admin_username.encode()) and hmac.compare_digest(password.encode(), settings.admin_password.encode())

def issue_session(response: Response):
    token = serializer.dumps({"u": settings.admin_username})
    response.set_cookie(COOKIE, token, httponly=True, secure=settings.app_public_url.startswith("https://"), samesite="strict", max_age=settings.session_max_age_seconds, path="/")

def clear_session(response: Response):
    response.delete_cookie(COOKIE, path="/")

async def require_admin(request: Request):
    token = request.cookies.get(COOKIE)
    if not token:
        raise HTTPException(401, "Please sign in")
    try:
        data = serializer.loads(token, max_age=2592000)
        if not isinstance(data, dict) or not data.get("u"):
            raise HTTPException(401, "Invalid session")
    except (BadSignature, SignatureExpired):
        raise HTTPException(401, "Session expired. Please sign in again")
    owner = data["u"]
    if owner != settings.admin_username:
        try: UUID(owner)
        except (ValueError, TypeError): raise HTTPException(401, "Invalid device session")
    if owner == settings.admin_username:
        try: serializer.loads(token, max_age=settings.session_max_age_seconds)
        except (BadSignature, SignatureExpired): raise HTTPException(401, "Session expired")
    current_owner.set(owner)
    return owner
