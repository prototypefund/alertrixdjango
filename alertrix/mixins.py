from django.contrib.auth.mixins import UserPassesTestMixin


class UserIsAdminForThisObjectMixin(
    UserPassesTestMixin,
):
    def test_func(self):
        return self.get_object().admins in self.request.user.groups.all()
