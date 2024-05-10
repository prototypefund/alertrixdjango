import abc

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


class UserIsAdminForThisObjectMixin(
    UserPassesTestMixin,
):
    def test_func(self):
        return self.get_object().admins in self.request.user.groups.all()
