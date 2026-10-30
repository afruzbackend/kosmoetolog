from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("xizmatlar/", views.catalog, name="catalog"),
    path("xizmat/<int:pk>/", views.service_detail, name="service"),
    path("shifokor/<int:pk>/", views.doctor_detail, name="doctor"),
    path("navbat/", views.booking_page, name="booking"),
    path("navbatim/", views.lookup, name="lookup"),
    path("til/<str:code>/", views.set_language, name="set_language"),
    path("api/search/", views.api_search, name="api_search"),
    path("api/doctors/", views.api_doctors, name="api_doctors"),
    path("api/month/", views.api_month, name="api_month"),
    path("api/slots/", views.api_slots, name="api_slots"),
    path("api/book/", views.api_book, name="api_book"),
    path("robots.txt", views.robots),
    path("favicon.ico", views.favicon),
]
