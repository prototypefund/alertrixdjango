from django.urls import include
from django.urls import path

from . import views


urlpatterns = [
    path('comp/', include([
        path('', views.company.ListCompanies.as_view(), name='comp.list'),
        path('new', views.company.CreateCompany.as_view(), name='comp.new'),
        path('<slug:slug>', views.company.DetailCompany.as_view(), name='comp.detail'),
        path('<slug:slug>/invite', views.company.InviteUser.as_view(), name='comp.invite'),
        path('<slug:slug>/edit', views.company.UpdateCompany.as_view(), name='comp.edit'),
    ])),
    path('appservice/', include([
    ]))
]
