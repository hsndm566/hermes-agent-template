import hmac
from fastapi import Request, Response
from itsdangerous import URLSafeTimedSerializer
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
    # TEMPORARY DEMO MODE: dashboard/API are intentionally open.
    # Keep this dependency in place so authentication can be restored later
    # without changing every protected route.
    return True
