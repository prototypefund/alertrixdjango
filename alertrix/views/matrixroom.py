import nio
import synapse.appservice
from asgiref.sync import async_to_sync
from django.conf import settings
from django.contrib import messages
from django.utils.translation import gettext_lazy as _

from matrixappservice import models as mas_models


class CreateMatrixRoom(
):
    """
    Parent CreateView to create MatrixRoom objects.
    """

    def get_form_kwargs(self):
        kwargs = {
            'user': self.request.user,
            **super().get_form_kwargs(),
        }
        return kwargs

    def get_matrix_room_args(self, form):
        """
        Return the arguments used to create the room.
        :param form:
        :return:
        """
        return dict(
        )

    def ensure_matrix_room_id(self, form):
        """
        Make sure this object has a valid matrix room associated
        :return:
        """
        if not self.object.matrix_room_id:
            alias_namespaces = mas_models.Namespace.objects.filter(
                app_service=self.object.handler.application_service,
                scope=mas_models.Namespace.ScopeChoices.aliases,
            )
            # Prepare the alias variable
            alias = None
            # Create a synapse instance to check if its application service is interested in the generated user id
            syn: synapse.appservice.ApplicationService = async_to_sync(
                self.object.handler.application_service.get_synapse_application_service
            )()
            for namespace in alias_namespaces:
                if '*' not in namespace.regex:
                    continue
                localpart = namespace.regex.lstrip('@').replace('*', self.object.slug)
                interested_check_against = '@%(localpart)s:%(server_name)s' % {
                    'localpart': localpart,
                    'server_name': self.object.handler.application_service.homeserver.server_name,
                }
                if not syn.is_interested_in_user(
                        user_id=interested_check_against,
                ):
                    continue
                # Overwrite user_id variable
                alias = interested_check_against
                messages.info(
                    self.request,
                    _('the matrix room alias has automatically been set to \"%(alias)s\"') % {
                        'alias': alias,
                    },
                )
                break
            matrix_space_id = async_to_sync(self.create_matrix_room)(
                alias=alias,
                name=form.data['name'],
                topic=form.data['description'],
                federate=form.data['federate'],
                initial_state=[
                    {
                        'type': 'm.room.member',
                        'content': {
                            'membership': 'join',
                            'displayname': form.data['name'],
                        },
                        'state_key': self.object.responsible_user.user_id,
                    },
                ],
                invite=(
                    [
                        str(self.request.user.matrix_id)
                    ]
                    if self.request.user.groups.filter(name=settings.MATRIX_VALIDATED_GROUP_NAME).exists() else None
                ),
                power_level_override=(
                    {
                        'users': {
                            self.object.responsible_user.user_id: 100,
                            str(self.request.user.matrix_id): 100,
                        },
                    }
                    if self.request.user.groups.filter(name=settings.MATRIX_VALIDATED_GROUP_NAME).exists() else None
                ),
                space=True,
                **self.get_matrix_room_args(
                    form=form,
                ),
            )
            if matrix_space_id:
                if self.request.user.matrix_id:
                    messages.success(
                        self.request,
                        _('%(user_id)s has been invited') % {
                            'user_id': self.request.user.matrix_id,
                        },
                    )
            self.object.matrix_room_id = matrix_space_id

    async def create_matrix_room(
            self,
            **kwargs,
    ):
        client: nio.AsyncClient = await self.object.responsible_user.get_client()
        response: nio.RoomCreateResponse = await client.room_create(
            **kwargs
        )
        if type(response) is nio.RoomCreateError:
            messages.warning(
                self.request,
                _('failed to create matrix space: %(errcode)s %(error)s') % {
                    'errcode': response.status_code,
                    'error': response.message,
                },
            )
            return None
        return response.room_id
