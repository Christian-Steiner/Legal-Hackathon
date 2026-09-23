"""Demo 'auth': the frontend role switcher sends X-Role (lawyer|client) and X-Actor (a display name).
Not real authentication (out of scope), but it lets the backend refuse lawyer-only actions."""
from fastapi import Header, HTTPException


def require_lawyer(x_role: str = Header(default=""), x_actor: str = Header(default="")) -> str:
    if x_role != "lawyer" or not x_actor.strip():
        raise HTTPException(403, "Only a named LEXR lawyer can do this (send X-Role: lawyer and X-Actor).")
    return f"lawyer:{x_actor.strip()}"


def actor(x_role: str = Header(default=""), x_actor: str = Header(default="")) -> str:
    return f"{x_role or 'anonymous'}:{x_actor.strip() or 'unknown'}"
