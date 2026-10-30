from django.conf import settings
from django.urls import include, path, re_path
from django.views.static import serve

from clinic import errors

urlpatterns = [
    path("panel/", include("clinic.panel_urls")),
    # Paneldan yuklangan rasmlar: faqat ImageField tekshiruvidan o'tgan fayllar
    re_path(r"^media/(?P<path>.*)$", serve, {"document_root": settings.MEDIA_ROOT}),
    path("", include("clinic.urls")),
]

if settings.DEBUG:
    urlpatterns.insert(0, re_path(r"^xato/(?P<name>400|403|404|500|csrf)/$", errors.preview))
    urlpatterns.append(re_path(r"^.*$", errors.dev_not_found))

handler400 = "clinic.errors.bad_request"
handler403 = "clinic.errors.permission_denied"
handler404 = "clinic.errors.not_found"
handler500 = "clinic.errors.server_error"
