from django.urls import path

from . import views


urlpatterns = [
    path('register', views.registration_or_first_user_view, name='register'),
    path('register/<matrix_id>', views.CreateUser.as_view(), name='validate'),
]
