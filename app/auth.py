from __future__ import annotations

from secrets import compare_digest
from urllib.parse import quote

from fastapi import HTTPException, Request, status


SESSION_AUTH_KEY = "authenticated"


def sanitize_next_path(next_path: str | None) -> str:
    if not next_path or not next_path.startswith("/") or next_path.startswith("//"):
        return "/"
    return next_path


def is_authenticated(request: Request) -> bool:
    settings = request.app.state.settings
    if not settings.auth_enabled:
        return True
    return bool(request.session.get(SESSION_AUTH_KEY))


def require_api_access(request: Request) -> None:
    if is_authenticated(request):
        return
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")


def login_redirect(next_path: str | None = "/") -> str:
    return f"/login?next={quote(sanitize_next_path(next_path), safe='')}"


def authenticate_session(request: Request, password: str) -> bool:
    settings = request.app.state.settings
    if not settings.auth_enabled:
        return True

    if compare_digest(password, settings.app_access_password or ""):
        request.session[SESSION_AUTH_KEY] = True
        return True

    request.session.clear()
    return False


def clear_session(request: Request) -> None:
    if hasattr(request, "session"):
        request.session.clear()
