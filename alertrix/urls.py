from django.urls import include
from django.urls import path

from . import views


urlpatterns = [
    path('', views.home, name='home'),
    path('setup/', include([
        path('channels/new', views.alert_channel.CreateAlertChannel.as_view(), name='alert_channel.new'),
    ])),
    path('public/', views.unit.PublicUnits.as_view(), name='public_units'),
    path('comp/', include([
        path('', views.company.ListCompanies.as_view(), name='comp.list'),
        path('new', views.company.CreateCompany.as_view(), name='comp.new'),
        path('<str:pk>', views.company.DetailCompany.as_view(), name='comp.detail'),
        path('<str:pk>/invite', views.company.InviteUser.as_view(), name='comp.invite'),
        path('<str:pk>/edit', views.company.UpdateCompany.as_view(), name='comp.edit'),
    ])),
    path('unit/', include([
        path('new', views.unit.CreateUnit.as_view(), name='unit.new'),
        path('<pk>', views.unit.UnitDetailView.as_view(), name='unit.detail'),
    ])),
    path('emergency/', include([
        path('alert/', include([
            path('new', views.emergency.AlertView.as_view(), name='alert.new'),
        ])),
    ])),
    path('appservice/', include([
        path('', views.appservice.ListApplicationServices.as_view(), name='appservice.list'),
        path('<slug:pk>', views.appservice.DetailApplicationService.as_view(), name='appservice.detail'),
        path('<slug:pk>/setup', views.appservice.SetupApplicationService.as_view(), name='appservice.setup'),
    ]))
]
