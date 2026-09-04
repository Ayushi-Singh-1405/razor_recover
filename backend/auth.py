#!/usr/bin/env python3
"""Google OAuth login + JWT session auth for merchant accounts.

Flow:
    GET /auth/google/login    -> redirect to Google consent screen
    GET /auth/google/callback -> exchange code, fetch profile, upsert
                                 merchant, issue JWT session cookie,
                                 redirect to the frontend dashboard
    GET /auth/me              -> current merchant info (or 401)
    GET /auth/logout          -> clear the session cookie

The session JWT is signed HS256 with JWT_SECRET and stored in an
httpOnly cookie ("recoverai_session") so browser JavaScript cannot read
it. get_current_merchant() is the dependency any protected route can use.
"""

import os
import uuid
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import jwt
import requests
from dotenv import load_dotenv
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from db import get_db
from models import Merchant

load_dotenv()

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "").strip()
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "").strip()
JWT_SECRET = os.getenv("JWT_SECRET", "").strip()

# Base URL of THIS backend (builds the OAuth redirect_uri that must match
# exactly what is registered in the Google Cloud console).
APP_BASE_URL = os.getenv("APP_BASE_URL", "http://localhost:8000").rstrip("/")
# Frontend base URL — redirect target after login/logout.
# The frontend (login/dashboard pages) is served by this backend itself.
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:8000").rstrip("/")
DASHBOARD_PATH = "/dashboard"

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"

SESSION_COOKIE_NAME = "recoverai_session"
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = 24

router = APIRouter(prefix="/auth", tags=["auth"])


def _require_google_config() -> None:
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        raise HTTPException(
            status_code=503,
            detail="Google OAuth is not configured: set GOOGLE_CLIENT_ID and "
                   "GOOGLE_CLIENT_SECRET in the environment.",
        )


def _require_jwt_secret() -> None:
    if not JWT_SECRET:
        raise HTTPException(
            status_code=503,
            detail="Session signing is not configured: set JWT_SECRET in the environment.",
        )


def _redirect_uri() -> str:
    return f"{APP_BASE_URL}/auth/google/callback"


def _issue_session_jwt(merchant: Merchant) -> str:
    """Sign an HS256 session token carrying the merchant id and email."""
    _require_jwt_secret()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(merchant.id),
        "email": merchant.email,
        "iat": now,
        "exp": now + timedelta(hours=JWT_EXPIRY_HOURS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


@router.get("/google/login")
def google_login():
    """Redirect the merchant to Google's OAuth consent screen."""
    _require_google_config()
    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": _redirect_uri(),
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "online",
        "prompt": "select_account",
    }
    return RedirectResponse(f"{GOOGLE_AUTH_URL}?{urlencode(params)}")


@router.get("/google/callback")
def google_callback(code: str = Query(...), db: Session = Depends(get_db)):
    """Exchange the authorization code for tokens, upsert the merchant,
    issue the session cookie, and redirect to the frontend dashboard."""
    _require_google_config()
    _require_jwt_secret()

    # 1. Exchange the authorization code for tokens.
    try:
        token_resp = requests.post(
            GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "redirect_uri": _redirect_uri(),
                "grant_type": "authorization_code",
            },
            timeout=15,
        )
    except requests.exceptions.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"Google token exchange failed: {exc}")

    if token_resp.status_code != 200:
        raise HTTPException(
            status_code=502,
            detail=f"Google token exchange returned HTTP {token_resp.status_code}",
        )
    access_token = token_resp.json().get("access_token")
    if not access_token:
        raise HTTPException(status_code=502, detail="Google token exchange returned no access_token")

    # 2. Fetch the merchant's Google profile (email, name).
    try:
        userinfo_resp = requests.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=15,
        )
    except requests.exceptions.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"Google userinfo fetch failed: {exc}")

    if userinfo_resp.status_code != 200:
        raise HTTPException(
            status_code=502,
            detail=f"Google userinfo returned HTTP {userinfo_resp.status_code}",
        )
    info = userinfo_resp.json()
    email = info.get("email")
    if not email:
        raise HTTPException(status_code=400, detail="Google account did not share an email address")
    name = info.get("name") or email

    # 3. Look up the merchant by email; create the row if none exists.
    merchant = db.query(Merchant).filter(Merchant.email == email).first()
    if merchant is None:
        merchant = Merchant(email=email, name=name)
        db.add(merchant)
        db.commit()
        db.refresh(merchant)
    elif merchant.name != name:
        merchant.name = name
        db.commit()

    # 4. Issue the signed session cookie and redirect to the dashboard.
    response = RedirectResponse(f"{FRONTEND_URL}{DASHBOARD_PATH}", status_code=303)
    # Secure flag when the deployment is HTTPS-based (Railway/Render/etc.);
    # localhost HTTP development keeps it disabled so login still works.
    response.set_cookie(
        SESSION_COOKIE_NAME,
        _issue_session_jwt(merchant),
        httponly=True,
        samesite="lax",
        secure=APP_BASE_URL.startswith("https://"),
        max_age=JWT_EXPIRY_HOURS * 3600,
    )
    return response


def get_current_merchant(request: Request, db: Session = Depends(get_db)) -> Merchant:
    """Dependency: verify the session JWT cookie and return the merchant.

    Raises 401 when the cookie is missing, the token is invalid or
    expired, or the merchant no longer exists.

    Usage — EVERY dashboard and escalation-action route must depend on
    this so it returns 401 without a valid session:

        from fastapi import Depends
        from auth import get_current_merchant

        @router.get("/dashboard/summary")
        def dashboard_summary(merchant: Merchant = Depends(get_current_merchant)):
            ...

        @router.post("/dashboard/escalations/{escalation_id}/approve")
        def approve_escalation(escalation_id: str,
                               merchant: Merchant = Depends(get_current_merchant)):
            ...

        @router.post("/dashboard/escalations/{escalation_id}/dismiss")
        def dismiss_escalation(escalation_id: str,
                               merchant: Merchant = Depends(get_current_merchant)):
            ...

    Planned protected routes (per the Phase 3/4 plan):
        GET  /dashboard/summary
        POST /dashboard/escalations/{id}/approve
        POST /dashboard/escalations/{id}/dismiss
    """
    _require_jwt_secret()
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Session expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid session token")

    sub = payload.get("sub")
    if not sub:
        raise HTTPException(status_code=401, detail="Invalid session token")

    try:
        merchant = db.get(Merchant, uuid.UUID(sub))
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid session token")
    if merchant is None:
        raise HTTPException(status_code=401, detail="Merchant not found")

    return merchant


@router.get("/me")
def auth_me(merchant: Merchant = Depends(get_current_merchant)):
    """Return the current merchant's info so the frontend can check
    login state on page load."""
    return {
        "id": str(merchant.id),
        "email": merchant.email,
        "name": merchant.name,
        "created_at": merchant.created_at.isoformat(),
    }


@router.get("/logout")
def auth_logout():
    """Clear the session cookie and redirect to the frontend."""
    response = RedirectResponse(f"{FRONTEND_URL}/", status_code=303)
    response.delete_cookie(SESSION_COOKIE_NAME)
    return response
