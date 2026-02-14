"""Preset registry for CLI wizard."""

from __future__ import annotations

from cli.presets.agriculture import get_preset as agriculture_preset
from cli.presets.professional_services import get_preset as professional_services_preset

PRESETS: dict[str, callable] = {
    "agriculture": agriculture_preset,
    "professional_services": professional_services_preset,
}
