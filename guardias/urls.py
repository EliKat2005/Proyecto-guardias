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
    path('turnos/<int:sede_id>/<path:ciclo>/', views.turnos_por_sede_ciclo, name='turnos_por_sede_ciclo'),
    path('rotacion/generar/', views.generar_rotacion, name='generar_rotacion'),
    path('turno/eliminar/<int:turno_id>/', views.eliminar_turno, name='eliminar_turno'),
    path('reportes/eventos/', views.eventos, name='eventos'),

    # NUEVAS 	6 SEDES
    path('sedes/', views.sedes_list, name='sedes_list'),
    path('sedes/<int:sede_id>/', views.sedes_detail, name='sedes_detail'),
    path('sedes/<int:sede_id>/ciclos/', views.sedes_ciclos, name='sedes_ciclos'),
    path('sedes/crear/', views.sede_crear, name='sede_crear'),
    path('sedes/<int:sede_id>/editar/', views.sede_editar, name='sede_editar'),
    path('sedes/<int:sede_id>/eliminar/', views.sede_eliminar, name='sede_eliminar'),

    # NUEVAS 	6 GUARDIAS
    path('guardias/', views.guardias_list, name='guardias_list'),
    path('guardias/alta/', views.guardia_alta, name='guardia_alta'),
    path('guardias/baja/', views.guardia_baja, name='guardia_baja'),
    path('guardias/<int:guardia_id>/editar/', views.guardia_editar, name='guardia_editar'),
    path('guardias/reactivar/', views.guardia_reactivar, name='guardia_reactivar'),
    path('guardias/<int:guardia_id>/eliminar/', views.guardia_eliminar, name='guardia_eliminar'),
    path('guardias/<int:guardia_id>/eliminar/info/', views.guardia_eliminar_info, name='guardia_eliminar_info'),

    # NUEVAS – JORNADAS (catálogo)
    path('jornadas/', views.jornadas_list, name='jornadas_list'),
    path('jornadas/cargar_defecto/', views.cargar_jornadas_defecto, name='cargar_jornadas_defecto'),

    # NUEVAS – REPORTES
    path('reportes/horas/', views.reporte_horas, name='reporte_horas'),        # JSON
    path('reportes/horas.csv', views.reporte_horas_csv, name='reporte_horas_csv'),  # CSV
    path('reportes/horas-diarias/', views.reporte_horas_diarias, name='reporte_horas_diarias'),  # Vista vw_horas_por_guardia_dia
    path('rotacion/eliminar/<int:sede_id>/<path:ciclo>/', views.rotacion_eliminar, name='rotacion_eliminar'),
    path('sedes/<int:sede_id>/eliminar/info/', views.sede_eliminar_info, name='sede_eliminar_info'),
]