from django.urls import path

from . import views

app_name = "ofrendas"

urlpatterns = [
    path("", views.list_profesor, name="list"),
    path("registrar/", views.registrar, name="registrar"),
]
