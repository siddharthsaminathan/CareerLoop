"""Supabase JWT verification.

Supabase issues HS256 JWTs signed with the project-level JWT secret
(Supabase dashboard → Settings → API → JWT Secret).

The client (web/@supabase/supabase-js, iOS/supabase-swift, Android/supabase-kt)
handles the OAuth flow and passes the resulting access_token as:
    Authorization: Bearer <access_token>

We verify the signature here and return the payload. No token minting on the
backend — Supabase owns the full auth lifecycle.

JWT payload claims we use:
  sub   — auth.users UUID (becomes careerloop.users.id)
  email — user's verified email
  user_metadata.full_name / user_metadata.name — from Google profile
  exp   — expiration
  role  — must be "authenticated"
"""

import logging
from typing import Optional

import jwt

from careerloop_api.core.config import settings

logger = logging.getLogger("careerloop_api.security")


def verify_supabase_jwt(token: str) -> dict:
    """Verify a Supabase-issued JWT. Returns the decoded payload.

    Raises ValueError with a human-readable reason on any failure.
    """
    secret = settings.SUPABASE_JWT_SECRET
    if not secret:
        raise ValueError(
            "SUPABASE_JWT_SECRET is not set. "
            "Add it to .env from Supabase dashboard → Settings → API → JWT Secret."
        )

    try:
        payload = jwt.decode(
            token,
            secret,
            algorithms=["HS256"],
            audience="authenticated",
            options={"verify_exp": True},
        )
    except jwt.ExpiredSignatureError:
        raise ValueError("Token has expired. Please sign in again.")
    except jwt.InvalidAudienceError:
        raise ValueError("Invalid token audience. Expected 'authenticated'.")
    except jwt.InvalidSignatureError:
        raise ValueError("Invalid token signature.")
    except jwt.DecodeError as e:
        raise ValueError(f"Malformed token: {e}")
    except jwt.PyJWTError as e:
        raise ValueError(f"Token verification failed: {e}")

    role = payload.get("role")
    if role != "authenticated":
        raise ValueError(f"Token role must be 'authenticated', got '{role}'.")

    return payload


def extract_user_info(payload: dict) -> dict:
    """Pull the fields we care about from a verified Supabase payload."""
    meta = payload.get("user_metadata") or {}
    return {
        "user_id": payload["sub"],
        "email": payload.get("email") or meta.get("email") or "",
        # Google OAuth puts the display name in user_metadata.full_name or .name
        "full_name": meta.get("full_name") or meta.get("name") or "",
        "avatar_url": meta.get("avatar_url") or meta.get("picture") or "",
        "provider": (payload.get("app_metadata") or {}).get("provider", ""),
    }
