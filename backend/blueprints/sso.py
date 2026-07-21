import os
from datetime import datetime, timezone

import jwt as pyjwt
from flask import Blueprint, current_app, make_response, redirect, request
from flask_jwt_extended import create_access_token, set_access_cookies

sso_bp = Blueprint("sso", __name__, url_prefix="/sso")

_SSO_ISSUER = "padikkunnundo"
_SSO_AUDIENCE = "mcq-quiz"
_SSO_ALGORITHM = "HS256"


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
    next_path = request.args.get("next", "/dashboard")

    if not next_path.startswith("/"):
        next_path = "/dashboard"

    if not token:
        return redirect("/?sso_error=missing_token")

    payload = _verify_sso_token(token)
    if payload is None:
        return redirect("/?sso_error=invalid_token")

    from backend.models import User, db

    sso_id = int(payload["sub"])
    name = payload.get("name", "")
    email = payload.get("email") or None

    user = User.query.filter_by(sso_id=sso_id).first()

    if user is None:
        base = (name or f"user_{sso_id}")[:80]
        username, suffix = base, 1
        while User.query.filter_by(username=username).first():
            username = f"{base[:76]}_{suffix}"
            suffix += 1

        user = User(
            username=username,
            email=email,
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
        user.last_sso_login = datetime.now(timezone.utc)
        db.session.commit()
        current_app.logger.info(f"SSO: returning user '{user.username}' (sso_id={sso_id})")

    access_token = create_access_token(identity=str(user.id))

    response = make_response(redirect(next_path))
    set_access_cookies(response, access_token)
    return response
