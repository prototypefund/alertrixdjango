import json
from dataclasses import dataclass
from django.template import loader


@dataclass
class Alert(
):
    code: str  # alarm keyword
    description: str = None
    units: list[str] = None  # list of the units matrix room ids
    location: tuple[float, float] = (None, None)  # latitude and longitude
    address: str = None
