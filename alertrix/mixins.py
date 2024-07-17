import abc

from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.mixins import UserPassesTestMixin
from django.urls import reverse


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
