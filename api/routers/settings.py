"""Settings endpoints — the runtime-tunable knobs behind the Settings page.

Thin pass-throughs to `merlin.services.app_settings`. A PATCH value of `null`
resets that knob to its env default; an unknown key or invalid value is a 400
(the service's ValueError).
"""

from __future__ import annotations

from fastapi import APIRouter, Body

from merlin.services import app_settings

from ..schemas import ModelsResponse, SettingsResponse

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("", response_model=SettingsResponse)
def get_settings():
    return app_settings.get_settings()


@router.patch("", response_model=SettingsResponse)
def update_settings(patch: dict[str, str | int | None] = Body(...)):
    return app_settings.update_settings(patch)


@router.get("/models", response_model=ModelsResponse)
def list_models():
    return app_settings.list_models()
