"""Data register API: externally sourced figures with provenance (actual / published / estimated / simulated)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from .. import data_register
from ..deps import CurrentUser

router = APIRouter(prefix="/data", tags=["data-register"])


@router.get("/register")
def register(p: CurrentUser, classification: str | None = None, agency: str | None = None):
    rows = data_register.REGISTER
    if classification:
        rows = [r for r in rows if r["classification"] == classification]
    if agency:
        a = agency.lower()
        rows = [r for r in rows if a in r["agency"].lower()]
    return rows


@router.get("/register/classifications")
def classifications(p: CurrentUser):
    return list(data_register.CLASSIFICATIONS)


@router.get("/register/{key}")
def register_entry(key: str, p: CurrentUser):
    r = data_register.get(key)
    if r is None:
        raise HTTPException(404, "No register entry with that key")
    return r
