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

    def __str__(self):
        res = loader.render_to_string(
            'alertrix/cli/emergency/alert.json',
            {
                'alert': self,
                'alert_html': json.dumps(loader.render_to_string(
                    'alertrix/emergency/alert.html',
                    {
                        'alert': self,
                    },
                )),
            },
        )
        return res
