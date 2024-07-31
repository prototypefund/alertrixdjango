import abc

from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.mixins import UserPassesTestMixin
from django.urls import reverse
from matrixappservice import models as mas_models


class ContextActionsMixin:
    context_actions = [
    ]

    def get_context_actions(self):
        for context_action in self.context_actions:
            if 'name' in context_action:
                context_action['url'] = reverse(context_action['name'])
        return self.context_actions


class UserIsInGroupForThisObjectMixin(
    UserPassesTestMixin,
    abc.ABC,
):
    allow_admins = True

    @property
    @abc.abstractmethod
    def group_attribute_name(self) -> str:
        return ''

    def test_func(self):
        return any([
            self.request.user.is_superuser,
            getattr(self.get_object(), self.group_attribute_name) in self.request.user.groups.all()
        ])


class UserIsAdminForThisObjectMixin(
    UserIsInGroupForThisObjectMixin,
):
    group_attribute_name = 'admins'


class UserIsUserOfThisObjectMixin(
    UserIsInGroupForThisObjectMixin,
):
    group_attribute_name = 'users'


class UserHasSpecificMembershipForThisMatrixRoom(
    UserPassesTestMixin,
):
    allow_admins = True
    valid_room_membership_states = [
        'invite',
        'join',
    ]

    def test_func(self):
        if self.request.user.is_superuser:
            return True
        try:
            assert self.object
        except AttributeError:
            self.object = self.get_object(self.get_queryset())
        try:
            mas_models.Event.objects.get(
                room__room_id=self.object.room_id,
                content__membership__in=self.valid_room_membership_states,
                state_key=self.request.user.matrix_id,
            )
            return True
        except mas_models.Event.DoesNotExist:
            pass
        return False


class MemberOrPublic(
    UserHasSpecificMembershipForThisMatrixRoom,
):
    def test_func(self):
        self.object = self.get_object(self.get_queryset())
        try:
            mas_models.Event.objects.get(
                room__room_id=self.object.room_id,
                type='m.room.join_rules',
                content__join_rule='public',
                state_key__isnull=False,
            )
            return True
        except mas_models.Event.DoesNotExist:
            return super().test_func()
