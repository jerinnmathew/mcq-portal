import uuid
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

import jwt as pyjwt
from flask import Blueprint, current_app, make_response, redirect, request
from flask_jwt_extended import create_access_token, set_access_cookies
from backend.utils.helpers import rate_limit

sso_bp = Blueprint("sso", __name__, url_prefix="/sso")

_SSO_ISSUER = "padikkunnundo"
_SSO_AUDIENCE = "mcq-quiz"
_SSO_ALGORITHM = "HS256"


def _sanitize_next_path(next_path: str) -> str:
    """Return a safe relative path, falling back to /dashboard on any suspicious input."""
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
    """Validate the incoming SSO JWT from padikkunnundo.app.

    Strictly enforces:
      - Signature (HMAC-SHA256 via SSO_JWT_SECRET)
      - Expiry (exp claim)
      - Audience must be exactly "mcq-quiz"
      - Issuer must be exactly "padikkunnundo"
    """
    secret = current_app.config.get("SSO_JWT_SECRET", "")
    if not secret:
        current_app.logger.error("SSO_JWT_SECRET is not configured")
        return None

    try:
        payload = pyjwt.decode(
            token,
            secret,
            algorithms=[_SSO_ALGORITHM],
            audience=_SSO_AUDIENCE,
            issuer=_SSO_ISSUER,
        )
        return payload
    except pyjwt.ExpiredSignatureError:
        current_app.logger.warning("SSO: token expired")
        return None
    except pyjwt.InvalidAudienceError:
        current_app.logger.warning("SSO: invalid audience claim")
        return None
    except pyjwt.InvalidIssuerError:
        current_app.logger.warning("SSO: invalid issuer claim")
        return None
    except pyjwt.PyJWTError as e:
        current_app.logger.warning(f"SSO: token invalid — {e}")
        return None


@sso_bp.route("/login")
@rate_limit(limit=120, period=60)
def sso_login():
    """Accept an SSO JWT from padikkunnundo.app, find or create the local user, and establish a session.

    Any request that does not carry a valid token is bounced back to the main
    site (PADIKKUNNUNDO_URL) so users are always forced to authenticate there first.
    """
    padikkunnundo_url = current_app.config.get("PADIKKUNNUNDO_URL", "https://padikkunnundo.app").rstrip("/")
    next_path = _sanitize_next_path(request.args.get("next", "/"))
    token = request.args.get("token", "").strip()

    if not token:
        current_app.logger.info("SSO: no token — redirecting to main site")
        return redirect(padikkunnundo_url)

    payload = _verify_sso_token(token)
    if payload is None:
        current_app.logger.info("SSO: invalid/expired token — redirecting to main site")
        return redirect(padikkunnundo_url)

    from backend.models import User, db

    try:
        sso_id = int(payload["sub"])
    except (KeyError, TypeError, ValueError):
        current_app.logger.warning("SSO: missing or non-numeric 'sub' claim")
        return redirect(padikkunnundo_url)

    email = payload.get("email", "").strip()
    if not email:
        current_app.logger.warning("SSO: missing email claim")
        return redirect(padikkunnundo_url)

    name = payload.get("name", "").strip() or None
    college = payload.get("college", "").strip() or None
    now = datetime.now(timezone.utc)

    user = User.query.filter_by(email=email).first()

    if user is None:
        base_username = (name or email.split("@")[0] or f"user_{sso_id}")[:76]
        # Check for any existing username starting with base_username in a single query
        collision = User.query.filter(User.username.like(f"{base_username}%")).count()
        username = base_username if collision == 0 else f"{base_username}_{uuid.uuid4().hex[:6]}"

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
            badge="Bronze",
            created_at=now,
            last_sso_login=now,
        )
        db.session.add(user)
        db.session.commit()
        current_app.logger.info(f"SSO: created user '{username}' (sso_id={sso_id})")
    else:
        user.sso_id = user.sso_id or sso_id
        user.name = name or user.name
        user.college = college or user.college
        user.is_sso_user = True
        user.last_sso_login = now
        db.session.commit()
        current_app.logger.info(f"SSO: returning user '{user.username}' (email={email})")

    access_token = create_access_token(identity=str(user.id))
    session_token = pyjwt.encode(
        {
            "sub": str(user.id),
            "exp": datetime.now(timezone.utc) + timedelta(days=30),
        },
        current_app.config["SECRET_KEY"],
        algorithm=_SSO_ALGORITHM,
    )

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
