from django.contrib import admin
from django.urls import path, include
from django.shortcuts import render
from django.db import connection

def home(request):
    # Traemos la lista de sedes (solo ID, nombre, ciudad) para el combo:
    with connection.cursor() as cur:
        cur.execute("SELECT sede_id, nombre, ciudad FROM sedes ORDER BY nombre, ciudad")
        rows = cur.fetchall()
    sedes = [{'sede_id': r[0], 'nombre': r[1], 'ciudad': r[2]} for r in rows]
    return render(request, "home.html", {'sedes': sedes})

urlpatterns = [
    path('', home, name='home'),
    path('admin/', admin.site.urls),
    path('api/', include('guardias.urls')),
]