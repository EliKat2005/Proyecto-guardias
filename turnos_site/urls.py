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


def sedes(request):
    # Lista simple de sedes para mostrar en la UI
    with connection.cursor() as cur:
        cur.execute("SELECT sede_id, nombre, ciudad, slot_minutos, max_guardias FROM sedes ORDER BY nombre, ciudad")
        rows = cur.fetchall()
    sedes = [{'sede_id': r[0], 'nombre': r[1], 'ciudad': r[2], 'slot_minutos': r[3], 'max_guardias': r[4]} for r in rows]
    return render(request, 'sedes.html', {'sedes': sedes})


def guardias(request):
    # Lista simple de guardias (join a sedes)
    with connection.cursor() as cur:
        cur.execute("""
            SELECT g.guardia_id, g.apellidos, g.nombres, g.activo, g.sede_id, s.nombre AS sede_nombre
            FROM guardias g
            LEFT JOIN sedes s ON s.sede_id = g.sede_id
            ORDER BY g.sede_id, g.orden_rotativo
        """)
        rows = cur.fetchall()
    guardias = [{'guardia_id': r[0], 'apellidos': r[1], 'nombres': r[2], 'activo': r[3], 'sede_id': r[4], 'sede_nombre': r[5]} for r in rows]
    return render(request, 'guardias.html', {'guardias': guardias})


def reportes(request):
    # Página de reportes con ejemplo de uso de endpoints JSON/CSV
    return render(request, 'reportes.html', {})


def jornadas(request):
    # Página de gestión de jornadas (catálogo)
    return render(request, 'jornadas.html', {})

urlpatterns = [
    path('', home, name='home'),
    path('sedes/', sedes, name='sedes'),
    path('guardias/', guardias, name='guardias'),
    path('jornadas/', jornadas, name='jornadas'),
    path('reportes/', reportes, name='reportes'),
    path('admin/', admin.site.urls),
    path('api/', include('guardias.urls')),
]