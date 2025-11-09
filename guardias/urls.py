try:
    from django.urls import path
except Exception:
    # Fallback stub so the editor / linter won't error if Django is not available.
    # In a real Django runtime, the real django.urls.path will be used.
    def path(route, view, name=None):
        return (route, view, name)

from . import views

urlpatterns = [
    # EXISTENTES
    path('turnos/<int:sede_id>/<slug:ciclo>/', views.turnos_por_sede_ciclo, name='turnos_por_sede_ciclo'),
    path('rotacion/generar/', views.generar_rotacion, name='generar_rotacion'),
    path('turno/eliminar/<int:turno_id>/', views.eliminar_turno, name='eliminar_turno'),
    path('reportes/eventos/', views.eventos, name='eventos'),

    # NUEVAS – SEDES
    path('sedes/', views.sedes_list, name='sedes_list'),
    path('sedes/crear/', views.sede_crear, name='sede_crear'),

    # NUEVAS – GUARDIAS
    path('guardias/', views.guardias_list, name='guardias_list'),
    path('guardias/alta/', views.guardia_alta, name='guardia_alta'),
    path('guardias/baja/', views.guardia_baja, name='guardia_baja'),

    # NUEVAS – JORNADAS (catálogo)
    path('jornadas/cargar_defecto/', views.cargar_jornadas_defecto, name='cargar_jornadas_defecto'),

    # NUEVAS – REPORTES
    path('reportes/horas/', views.reporte_horas, name='reporte_horas'),        # JSON
    path('reportes/horas.csv', views.reporte_horas_csv, name='reporte_horas_csv'),  # CSV
]