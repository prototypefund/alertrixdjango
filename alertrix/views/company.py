from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView
from .. import models


class ListCompanies(
    LoginRequiredMixin,
    ListView,
):
    model = models.Company
    template_name = 'alertrix/company_list.html'

    def get_queryset(self):
        queryset = self.model.objects.filter(
            admins__in=self.request.user.groups.all(),
        )
        ordering = self.get_ordering()
        if ordering:
            if isinstance(ordering, str):
                ordering = (ordering,)
            queryset = queryset.order_by(*ordering)
        return queryset
