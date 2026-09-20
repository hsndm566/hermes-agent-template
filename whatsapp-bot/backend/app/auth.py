import hmac
from fastapi import HTTPException, Request, Response
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from .config import settings

serializer = URLSafeTimedSerializer(settings.session_secret, salt="admin-session")
COOKIE = "booking_admin"

def valid_credentials(username: str, password: str) -> bool:
    return hmac.compare_digest(username, settings.admin_username) and hmac.compare_digest(password, settings.admin_password)

def issue_session(response: Response):
    token = serializer.dumps({"u": settings.admin_username})
    response.set_cookie(COOKIE, token, httponly=True, secure=True, samesite="strict", max_age=settings.session_max_age_seconds, path="/")

def clear_session(response: Response):
    response.delete_cookie(COOKIE, path="/")

def require_admin(request: Request):
    token = request.cookies.get(COOKIE)
    if not token:
        raise HTTPException(401, "Not authenticated")
    try:
        data = serializer.loads(token, max_age=settings.session_max_age_seconds)
    except (BadSignature, SignatureExpired):
        raise HTTPException(401, "Session expired")
    if not isinstance(data, dict) or data.get("u") != settings.admin_username:
        raise HTTPException(401, "Invalid session")
    return True