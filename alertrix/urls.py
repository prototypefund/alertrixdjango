from django.urls import include
from django.urls import path

from . import views


urlpatterns = [
    path('comp/', include([
        path('', views.company.ListCompanies.as_view(), name='comp.list'),
    ])),
]
