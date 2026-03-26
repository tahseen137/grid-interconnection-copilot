from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import User
from app.security import hash_password, verify_password


def _now() -> datetime:
    return datetime.now(UTC)


def _coerce_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def normalize_username(username: str) -> str:
    return username.strip().casefold()


def list_users(session: Session) -> list[User]:
    statement = select(User).order_by(User.created_at.asc(), User.username.asc())
    return list(session.scalars(statement))


def get_user_by_id(session: Session, user_id: str) -> User | None:
    return session.get(User, user_id)


def get_user_by_username(session: Session, username: str) -> User | None:
    normalized = normalize_username(username)
    statement = select(User).where(User.username == normalized)
    return session.scalars(statement).first()


def has_users(session: Session) -> bool:
    statement = select(func.count()).select_from(User)
    return bool(session.scalar(statement))


def count_active_admins(session: Session) -> int:
    statement = select(func.count()).select_from(User).where(User.role == "admin", User.is_active.is_(True))
    return int(session.scalar(statement) or 0)


def create_user(
    session: Session,
    *,
    username: str,
    password: str,
    role: str,
    full_name: str = "",
    is_active: bool = True,
) -> User:
    normalized_username = normalize_username(username)
    if get_user_by_username(session, normalized_username):
        raise ValueError("A user with that username already exists")

    user = User(
        username=normalized_username,
        full_name=full_name.strip(),
        password_hash=hash_password(password),
        role=role,
        is_active=is_active,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def update_user_password(session: Session, user: User, password: str) -> User:
    user.password_hash = hash_password(password)
    user.failed_login_attempts = 0
    user.locked_until = None
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def update_user(
    session: Session,
    user: User,
    *,
    full_name: str | None = None,
    role: str | None = None,
    is_active: bool | None = None,
    password: str | None = None,
    acting_user: User | None = None,
) -> User:
    target_role = role if role is not None else user.role
    target_is_active = is_active if is_active is not None else user.is_active

    is_last_active_admin = user.role == "admin" and user.is_active and count_active_admins(session) <= 1
    if is_last_active_admin and (target_role != "admin" or not target_is_active):
        raise ValueError("Keep at least one active admin account in the workspace")
    if acting_user and acting_user.id == user.id and is_active is False:
        raise ValueError("You cannot deactivate your own account")

    if full_name is not None:
        user.full_name = full_name.strip()
    if role is not None:
        user.role = role
    if is_active is not None:
        user.is_active = is_active
    if password:
        user.password_hash = hash_password(password)
        user.failed_login_attempts = 0
        user.locked_until = None

    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def ensure_bootstrap_admin(session: Session, settings: Settings) -> User | None:
    fallback_username = "admin" if settings.app_access_password and not settings.bootstrap_admin_username else None
    bootstrap_username = settings.bootstrap_admin_username or fallback_username
    bootstrap_password = settings.bootstrap_admin_password or settings.app_access_password

    if not (bootstrap_username and bootstrap_password):
        return None

    existing_user = get_user_by_username(session, bootstrap_username)
    if existing_user:
        return existing_user

    return create_user(
        session,
        username=bootstrap_username,
        password=bootstrap_password,
        role="admin",
        full_name="Workspace Administrator",
        is_active=True,
    )


@dataclass
class AuthResult:
    user: User | None
    error: str | None = None


def authenticate_user(session: Session, username: str, password: str, settings: Settings) -> AuthResult:
    user = get_user_by_username(session, username)
    if user is None or not user.is_active:
        return AuthResult(user=None, error="Invalid credentials")

    now = _now()
    locked_until = _coerce_utc(user.locked_until)
    if locked_until and locked_until > now:
        return AuthResult(user=None, error="Account temporarily locked. Try again later.")

    if not verify_password(password, user.password_hash):
        user.failed_login_attempts += 1
        if user.failed_login_attempts >= settings.max_login_attempts:
            user.locked_until = now + timedelta(minutes=settings.login_lockout_minutes)
            user.failed_login_attempts = 0
        session.add(user)
        session.commit()
        locked_until = _coerce_utc(user.locked_until)
        if locked_until and locked_until > now:
            return AuthResult(user=None, error="Account temporarily locked. Try again later.")
        return AuthResult(user=None, error="Invalid credentials")

    user.failed_login_attempts = 0
    user.locked_until = None
    user.last_login_at = now
    session.add(user)
    session.commit()
    session.refresh(user)
    return AuthResult(user=user)


def can_write(user: User | None) -> bool:
    return bool(user and user.role in {"admin", "analyst"})


def can_manage_users(user: User | None) -> bool:
    return bool(user and user.role == "admin")
