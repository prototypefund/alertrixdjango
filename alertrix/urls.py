from django.urls import include
from django.urls import path

from . import views


urlpatterns = [
    path('comp/', include([
        path('', views.company.ListCompanies.as_view(), name='comp.list'),
        path('<slug:slug>', views.company.DetailCompany.as_view(), name='comp.detail'),
        path('<slug:slug>/invite', views.company.InviteUser.as_view(), name='comp.invite'),
    ])),
]
