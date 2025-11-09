# This is an auto-generated Django model module.
# You'll have to do the following manually to clean this up:
#   * Rearrange models' order
#   * Make sure each model has one field with primary_key=True
#   * Make sure each ForeignKey and OneToOneField has `on_delete` set to the desired behavior
#   * Remove `managed = False` lines if you wish to allow Django to create, modify, and delete the table
# Feel free to rename the models, but don't rename db_table values or field names.
from django.db import models


class Sedes(models.Model):
    sede_id = models.FloatField(primary_key=True)
    nombre = models.CharField(max_length=100)
    ciudad = models.CharField(max_length=100)
    slot_minutos = models.FloatField()
    max_guardias = models.FloatField()
    activo = models.CharField(max_length=1, blank=True, null=True)
    creado_en = models.DateField()

    class Meta:
        managed = False
        db_table = 'sedes'
        unique_together = (('nombre', 'ciudad'),)


class Guardias(models.Model):
    guardia_id = models.FloatField(primary_key=True)
    sede = models.ForeignKey(Sedes, models.DO_NOTHING)
    apellidos = models.CharField(max_length=120)
    nombres = models.CharField(max_length=120)
    sueldo = models.DecimalField(max_digits=12, decimal_places=2)
    horas_trabajadas = models.DecimalField(max_digits=12, decimal_places=2)
    orden_rotativo = models.FloatField()
    activo = models.CharField(max_length=1, blank=True, null=True)
    fecha_ingreso = models.DateField()

    class Meta:
        managed = False
        db_table = 'guardias'
        unique_together = (('sede', 'orden_rotativo'),)


class Jornadas(models.Model):
    jornada_id = models.FloatField(primary_key=True)
    nombre = models.CharField(unique=True, max_length=50)
    hora_ini_ref = models.DurationField()
    hora_fin_ref = models.DurationField()

    class Meta:
        managed = False
        db_table = 'jornadas'


class Turnos(models.Model):
    turno_id = models.FloatField(primary_key=True)
    sede = models.ForeignKey(Sedes, models.DO_NOTHING)
    ciclo_fecha = models.DateField()
    guardia = models.ForeignKey(Guardias, models.DO_NOTHING)
    inicio = models.DateField()
    fin = models.DateField()
    jornada = models.ForeignKey(Jornadas, models.DO_NOTHING, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'turnos'


class ReporteEventos(models.Model):
    reporte_id = models.FloatField(primary_key=True)
    fecha_evento = models.DateField()
    tipo_evento = models.CharField(max_length=50)
    sede_id = models.FloatField(blank=True, null=True)
    guardia_id = models.FloatField(blank=True, null=True)
    turno_id = models.FloatField(blank=True, null=True)
    detalle = models.TextField(blank=True, null=True)
    creado_en = models.DateField()

    class Meta:
        managed = False
        db_table = 'reporte_eventos'
