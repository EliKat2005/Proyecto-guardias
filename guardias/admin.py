from django.contrib import admin
from .models import Sedes, Guardias, Jornadas, Turnos, ReporteEventos


@admin.register(Sedes)
class SedesAdmin(admin.ModelAdmin):
    list_display = ("sede_id", "nombre", "ciudad", "activo", "slot_minutos", "max_guardias")
    search_fields = ("nombre", "ciudad")


@admin.register(Guardias)
class GuardiasAdmin(admin.ModelAdmin):
    list_display = ("guardia_id", "apellidos", "nombres", "sueldo", "horas_trabajadas", "activo")
    list_filter = ("activo", "sede")
    search_fields = ("apellidos", "nombres")


@admin.register(Jornadas)
class JornadasAdmin(admin.ModelAdmin):
    list_display = ("jornada_id", "nombre", "hora_ini_ref", "hora_fin_ref")
    search_fields = ("nombre",)


@admin.register(Turnos)
class TurnosAdmin(admin.ModelAdmin):
    list_display = ("turno_id", "sede", "ciclo_fecha", "guardia", "inicio", "fin", "jornada")
    list_filter = ("sede", "ciclo_fecha", "jornada")
    search_fields = ("guardia__apellidos", "guardia__nombres")


@admin.register(ReporteEventos)
class ReporteEventosAdmin(admin.ModelAdmin):
    list_display = ("reporte_id", "fecha_evento", "tipo_evento", "sede_id", "guardia_id", "turno_id")
    list_filter = ("tipo_evento",)
    search_fields = ("detalle",)
