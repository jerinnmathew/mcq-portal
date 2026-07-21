from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

import jwt as pyjwt
from flask import Blueprint, current_app, make_response, redirect, request
from flask_jwt_extended import create_access_token, set_access_cookies

sso_bp = Blueprint("sso", __name__, url_prefix="/sso")

_SSO_ISSUER = "padikkunnundo"
_SSO_AUDIENCE = "mcq-quiz"
_SSO_ALGORITHM = "HS256"


def _sanitize_next_path(next_path: str) -> str:
    if not next_path:
        return "/dashboard"

    parsed = urlparse(next_path)
    if parsed.scheme or parsed.netloc:
        return "/dashboard"

    path = parsed.path
    if not path.startswith("/") or path.startswith("//"):
        return "/dashboard"

    if path == "/dashboard.html":
        path = "/dashboard"

    result = path
    if parsed.query:
        result = f"{result}?{parsed.query}"
    if parsed.fragment:
        result = f"{result}#{parsed.fragment}"
    return result


def _verify_sso_token(token: str) -> dict | None:
    """Validate the incoming SSO JWT from padikkunnundo.app."""
    secret = current_app.config.get("SSO_JWT_SECRET", "")
    if not secret:
        current_app.logger.error("SSO_JWT_SECRET is not configured")
        return None

    try:
        return pyjwt.decode(
            token,
            secret,
            algorithms=[_SSO_ALGORITHM],
            audience=_SSO_AUDIENCE,
            issuer=_SSO_ISSUER,
        )
    except pyjwt.ExpiredSignatureError:
        current_app.logger.warning("SSO: token expired")
        return None
    except pyjwt.PyJWTError as e:
        current_app.logger.warning(f"SSO: token invalid — {e}")
        return None


@sso_bp.route("/login")
def sso_login():
    """Accept an SSO JWT, create or update the local user, and log them in."""
    token = request.args.get("token", "").strip()
    next_path = _sanitize_next_path(request.args.get("next", "/dashboard"))

    if not token:
        return redirect("/login?error=missing_token")

    payload = _verify_sso_token(token)
    if payload is None:
        return redirect("/login?error=invalid_token")

    from backend.models import User, db

    try:
        sso_id = int(payload["sub"])
    except (KeyError, TypeError, ValueError):
        return redirect("/login?error=invalid_token")

    email = payload.get("email")
    if not email:
        return redirect("/login?error=invalid_token")

    name = payload.get("name", "").strip() or None
    college = payload.get("college", "").strip() or None

    user = User.query.filter_by(email=email).first()

    if user is None:
        base_username = (name or email.split("@")[0] or f"user_{sso_id}")[:80]
        username = base_username
        suffix = 1
        while User.query.filter_by(username=username).first():
            username = f"{base_username[:76]}_{suffix}"
            suffix += 1

        user = User(
            username=username,
            email=email,
            name=name,
            college=college,
            password_hash=None,
            sso_id=sso_id,
            is_sso_user=True,
            streak=0,
            xp_points=0,
            badge="Beginner",
            created_at=datetime.now(timezone.utc),
            last_sso_login=datetime.now(timezone.utc),
        )
        db.session.add(user)
        db.session.commit()
        current_app.logger.info(f"SSO: created new user '{username}' (sso_id={sso_id})")
    else:
        user.sso_id = user.sso_id or sso_id
        user.name = name or user.name
        user.college = college or user.college
        user.is_sso_user = True
        user.last_sso_login = datetime.now(timezone.utc)
        db.session.commit()
        current_app.logger.info(f"SSO: returning user '{user.username}' (email={email})")

    access_token = create_access_token(identity=str(user.id))
    session_token = pyjwt.encode(
        {
            "sub": str(user.id),
            "exp": datetime.utcnow() + timedelta(days=30),
        },
        current_app.config["SECRET_KEY"],
        algorithm=_SSO_ALGORITHM,
    )
    if isinstance(session_token, bytes):
        session_token = session_token.decode("utf-8")

    response = make_response(redirect(next_path))
    set_access_cookies(response, access_token)
    response.set_cookie(
        "session_token",
        session_token,
        max_age=30 * 24 * 3600,
        httponly=True,
        samesite="Lax",
        secure=not current_app.debug,
    )
    return response
