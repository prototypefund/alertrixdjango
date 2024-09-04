import json
from dataclasses import dataclass

from django.conf import settings
from django.template import loader


class Event(
):
    version: str = settings.ALERTRIX_VERSION
    type: str = None
    content: dict = None
    state_key: dict = None

    def get_type(self):
        return self.type

    def get_content(self):
        return {
            'version': self.version,
            **(self.content or dict()),
        }

    def get_state_key(self):
        return self.state_key

    def get_matrix_data(self, **kwargs):
        return {
            k: v
            for k, v in {
                'type': self.get_type(),
                'content': self.get_content(),
                'state_key': self.get_state_key(),
                **kwargs,
            }.items()
            if None not in [k, v]
        }

    def __str__(self):
        return json.dumps(
            self.get_matrix_data(),
        )


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
