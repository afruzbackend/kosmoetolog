from django.urls import path

from . import panel_views as v

app_name = "panel"

urlpatterns = [
    path("kirish/", v.login_view, name="login"),
    path("chiqish/", v.logout_view, name="logout"),
    path("", v.dashboard, name="dashboard"),
    path("kalendar/", v.calendar, name="calendar"),
    path("navbatlar/", v.appointments, name="appointments"),
    path("navbat/yangi/", v.appointment_form, name="appointment_new"),
    path("navbat/<int:pk>/", v.appointment_form, name="appointment"),
    path("navbat/<int:pk>/holat/", v.appointment_status, name="appointment_status"),
    path("mijozlar/", v.clients, name="clients"),
    path("mijoz/<int:pk>/", v.client_card, name="client"),
    path("api/mijoz/", v.client_lookup, name="client_lookup"),
    path("hisobot/", v.report, name="report"),
    path("hisobot/excel/", v.report_excel, name="report_excel"),
    path("sozlamalar/", v.settings_page, name="settings"),
    path("profil/", v.profile, name="profile"),
    path("r/<slug:slug>/", v.crud_list, name="crud"),
    path("r/<slug:slug>/yangi/", v.crud_form, name="crud_new"),
    path("r/<slug:slug>/<int:pk>/", v.crud_form, name="crud_edit"),
    path("r/<slug:slug>/<int:pk>/ochirish/", v.crud_delete, name="crud_delete"),
]
