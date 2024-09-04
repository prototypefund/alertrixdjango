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
    Event,
):
    type = 'm.room.message'
    code: str  # alarm keyword
    description: str = None
    units: list[str] = None  # list of the units matrix room ids
    location: tuple[float, float] = (None, None)  # latitude and longitude
    address: str = None

    def get_content(self):
        res = json.loads(loader.render_to_string(
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
        ))
        return res


@dataclass
class AlertrixCompany(
    Event,
):
    type = '%(prefix)s.company' % {
        'prefix': settings.ALERTRIX_STATE_EVENT_PREFIX,
    }
    inbox: str = None  # the matrix id of an alertrix compatible account
    state_key = ''

    def get_content(self):
        return {
            **super().get_content(),
            **{
                'inbox': self.inbox,
            },
        }


@dataclass
class AlertrixCompanyUnit(
    Event,
):
    type = '%(prefix)s.company.unit' % {
        'prefix': settings.ALERTRIX_STATE_EVENT_PREFIX,
    }
    child_room_id: str = None

    def get_state_key(self):
        return self.child_room_id
