from django.http import JsonResponse, HttpResponseBadRequest, HttpResponse
from django.db import connection
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from datetime import datetime

import json
import csv
import oracledb as Database  # para OUT binds en PL/SQL

def _query(sql, params=None):
    with connection.cursor() as cur:
        cur.execute(sql, params or {})
        cols = [c[0].lower() for c in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]

@require_http_methods(["GET"])
def turnos_por_sede_ciclo(request, sede_id, ciclo):
    # ciclo puede venir como 'YYYY-MM-DD_HH:MI' o 'YYYY-MM-DDTHH:MI' (datetime-local)
    # Convertir a formato Oracle: 'YYYY-MM-DD HH24:MI'
    ciclo_dt = ciclo.replace('_', ' ').replace('T', ' ')
    
    sql = """
    SELECT t.turno_id,
           g.apellidos || ', ' || g.nombres AS guardia,
           TO_CHAR(t.inicio,'YYYY-MM-DD HH24:MI') AS inicio,
           TO_CHAR(t.fin,   'YYYY-MM-DD HH24:MI') AS fin,
           ROUND((t.fin - t.inicio)*24,2) AS horas,
           j.nombre AS jornada
    FROM turnos t
    JOIN guardias g ON g.guardia_id = t.guardia_id
    LEFT JOIN jornadas j ON j.jornada_id = t.jornada_id
    WHERE t.sede_id = :sede
      AND t.ciclo_fecha = TO_DATE(:ciclo, 'YYYY-MM-DD HH24:MI')
    ORDER BY t.inicio
    """
    data = _query(sql, {'sede': sede_id, 'ciclo': ciclo_dt})
    return JsonResponse({'sede_id': sede_id, 'ciclo': ciclo_dt, 'turnos': data})

@csrf_exempt
@require_http_methods(["POST"])
def generar_rotacion(request):
    data = json.loads(request.body)
    sede_id = data.get('sede_id')
    ciclo = data.get('ciclo')
    inicio = data.get('inicio')
    
    # Convertir formato datetime-local (YYYY-MM-DDTHH:MM) a formato Oracle
    # El input datetime-local envía: "2025-11-09T13:46"
    ciclo_formatted = ciclo.replace('T', ' ') if ciclo and 'T' in ciclo else ciclo
    inicio_formatted = inicio.replace('T', ' ') if inicio and 'T' in inicio else inicio
    
    plsql = """
    BEGIN
      pkg_guardias.generar_rotacion(
        p_sede_id     => :sede,
        p_ciclo_fecha => TO_DATE(:ciclo, 'YYYY-MM-DD HH24:MI'),
        p_hora_inicio => TO_DATE(:inicio,'YYYY-MM-DD HH24:MI')
      );
    END;
    """
    with connection.cursor() as cur:
        cur.execute(plsql, {'sede': sede_id, 'ciclo': ciclo_formatted, 'inicio': inicio_formatted})
    return JsonResponse({'status': 'ok', 'message': 'Rotación generada'})

@csrf_exempt
@require_http_methods(["POST"])
def eliminar_turno(request, turno_id):
    plsql = """
    BEGIN
      pkg_guardias.eliminar_turno_y_ajustar(p_turno_id => :turno);
    END;
    """
    with connection.cursor() as cur:
        cur.execute(plsql, {'turno': turno_id})
    return JsonResponse({'status': 'ok', 'message': f'Turno {turno_id} eliminado y vecinos ajustados'})

@require_http_methods(["GET"])
def eventos(request):
    data = _query("""
      SELECT reporte_id, tipo_evento,
             TO_CHAR(fecha_evento,'YYYY-MM-DD HH24:MI:SS') AS fecha_evento,
             sede_id, guardia_id, turno_id,
             detalle
      FROM reporte_eventos
      ORDER BY fecha_evento DESC
    """)
    # Asegurar que los campos CLOB/LOB se conviertan a texto legible
    for row in data:
        if 'detalle' in row and row['detalle'] is not None:
            try:
                v = row['detalle']
                # Si es un LOB con método read()
                if hasattr(v, 'read'):
                    txt = v.read()
                else:
                    txt = str(v)
                row['detalle'] = txt[:160]
            except Exception:
                # Fallback a string simple
                try:
                    row['detalle'] = str(row['detalle'])[:160]
                except Exception:
                    row['detalle'] = ''
    return JsonResponse({'eventos': data})



# ======================

# SEDES
# ======================
@require_http_methods(["GET"])
def sedes_list(request):
        rows = _query("""
                SELECT sede_id, nombre, ciudad, slot_minutos, max_guardias, activo, TO_CHAR(creado_en,'YYYY-MM-DD HH24:MI:SS') creado_en
                FROM sedes
                ORDER BY nombre, ciudad
        """)
        return JsonResponse({'sedes': rows})

@require_http_methods(["GET"])
def sedes_detail(request, sede_id):
    rows = _query("""
        SELECT sede_id, nombre, ciudad, slot_minutos, max_guardias, activo, TO_CHAR(creado_en,'YYYY-MM-DD HH24:MI:SS') creado_en
        FROM sedes WHERE sede_id = :sede
    """, {'sede': sede_id})
    if not rows:
        return HttpResponse(status=404)
    return JsonResponse({'sede': rows[0]})

@csrf_exempt
@require_http_methods(["POST"])
def sede_crear(request):
        try:
                payload = json.loads(request.body.decode())
                nombre = payload['nombre']
                ciudad = payload['ciudad']
                slot   = int(payload.get('slot_minutos', 120))
                maxg   = int(payload.get('max_guardias', 10))
        except Exception as e:
                return HttpResponseBadRequest(f'JSON inválido: {e}')

        with connection.cursor() as cur:
                out_id = cur.var(Database.NUMBER)
                cur.execute("""
                        BEGIN
                            pkg_guardias.crear_sede(
                                p_nombre       => :p_nombre,
                                p_ciudad       => :p_ciudad,
                                p_slot_minutos => :p_slot,
                                p_max_guardias => :p_max,
                                p_sede_id      => :p_id
                            );
                        END;
                """, {'p_nombre': nombre, 'p_ciudad': ciudad, 'p_slot': slot, 'p_max': maxg, 'p_id': out_id})
                sede_id = int(out_id.getvalue())
        return JsonResponse({'status': 'ok', 'sede_id': sede_id})


@csrf_exempt
@require_http_methods(["POST"])
def sede_editar(request, sede_id):
    try:
        payload = json.loads(request.body.decode())
    except Exception as e:
        return HttpResponseBadRequest(f'JSON inválido: {e}')

    fields = []
    params = {}
    if 'nombre' in payload:
        fields.append('nombre = :nombre')
        params['nombre'] = payload['nombre']
    if 'ciudad' in payload:
        fields.append('ciudad = :ciudad')
        params['ciudad'] = payload['ciudad']
    if 'slot_minutos' in payload:
        fields.append('slot_minutos = :slot')
        params['slot'] = int(payload['slot_minutos'])
    if 'max_guardias' in payload:
        fields.append('max_guardias = :maxg')
        params['maxg'] = int(payload['max_guardias'])
    if 'activo' in payload:
        fields.append('activo = :activo')
        params['activo'] = payload['activo']

    if not fields:
        return HttpResponseBadRequest('Nada que actualizar')

    params['sede'] = sede_id
    sql = f"UPDATE sedes SET {', '.join(fields)} WHERE sede_id = :sede"
    with connection.cursor() as cur:
        cur.execute(sql, params)
    return JsonResponse({'status': 'ok', 'sede_id': sede_id})


# ======================
# GUARDIAS
# ======================
@require_http_methods(["GET"])
def guardias_list(request):
        # filtros opcionales: sede_id, activo(S/N)
        sede_id = request.GET.get('sede_id')
        activo  = request.GET.get('activo')
        sql = """
        SELECT g.guardia_id, g.apellidos, g.nombres, g.sueldo, g.horas_trabajadas,
                     g.orden_rotativo, g.activo, TO_CHAR(g.fecha_ingreso,'YYYY-MM-DD') fecha_ingreso,
                     g.sede_id, s.nombre AS sede_nombre, s.ciudad AS sede_ciudad
        FROM guardias g
        JOIN sedes s ON s.sede_id = g.sede_id
        WHERE (:sede_id IS NULL OR g.sede_id = :sede_id)
            AND (:activo  IS NULL OR g.activo  = :activo)
        ORDER BY g.sede_id, g.orden_rotativo
        """
        rows = _query(sql, {'sede_id': sede_id, 'activo': activo})
        return JsonResponse({'guardias': rows})

@csrf_exempt
@require_http_methods(["POST"])
def guardia_alta(request):
        try:
                payload = json.loads(request.body.decode())
                sede_id   = int(payload['sede_id'])
                apellidos = payload['apellidos']
                nombres   = payload['nombres']
                sueldo    = float(payload.get('sueldo', 0))
                orden     = int(payload['orden_rotativo'])
        except Exception as e:
                return HttpResponseBadRequest(f'JSON inválido: {e}')

        with connection.cursor() as cur:
                out_id = cur.var(Database.NUMBER)
                cur.execute("""
                BEGIN
                    pkg_guardias.alta_guardia(
                        p_sede_id        => :p_sede,
                        p_apellidos      => :p_ape,
                        p_nombres        => :p_nom,
                        p_sueldo         => :p_sue,
                        p_orden_rotativo => :p_ord,
                        p_guardia_id     => :p_id
                    );
                END;
                """, {'p_sede': sede_id, 'p_ape': apellidos, 'p_nom': nombres, 'p_sue': sueldo, 'p_ord': orden, 'p_id': out_id})
                guardia_id = int(out_id.getvalue())
        return JsonResponse({'status': 'ok', 'guardia_id': guardia_id})


@csrf_exempt
@require_http_methods(["POST"])
def guardia_baja(request):
    """
    Body JSON: {"guardia_id": 8, "desde_ciclo": "YYYY-MM-DD HH:MM"}  # opcional
    """
    try:
        payload = json.loads(request.body.decode())
        guardia_id = int(payload['guardia_id'])
        desde_ciclo = payload.get('desde_ciclo')
    except Exception as e:
        return HttpResponseBadRequest(f'JSON inválido: {e}')

    # Parseamos a datetime si viene cadena, o None si no viene.
    dt = None
    if desde_ciclo:
        try:
            dt = datetime.strptime(desde_ciclo, "%Y-%m-%d %H:%M")
        except ValueError:
            return HttpResponseBadRequest("Formato de 'desde_ciclo' inválido. Use 'YYYY-MM-DD HH:MM'.")

    with connection.cursor() as cur:
        cur.execute("""
        BEGIN
          pkg_guardias.baja_guardia(
            p_guardia_id        => :p_id,
            p_desde_ciclo_fecha => :p_fecha
          );
        END;
        """, {'p_id': guardia_id, 'p_fecha': dt})  # dt o None
    return JsonResponse({'status': 'ok'})


@csrf_exempt
@require_http_methods(["POST"])
def guardia_editar(request, guardia_id):
    try:
        payload = json.loads(request.body.decode())
    except Exception as e:
        return HttpResponseBadRequest(f'JSON inválido: {e}')

    fields = []
    params = {}
    if 'apellidos' in payload:
        fields.append('apellidos = :apellidos')
        params['apellidos'] = payload['apellidos']
    if 'nombres' in payload:
        fields.append('nombres = :nombres')
        params['nombres'] = payload['nombres']
    if 'sueldo' in payload:
        fields.append('sueldo = :sueldo')
        params['sueldo'] = float(payload['sueldo'])
    if 'orden_rotativo' in payload:
        fields.append('orden_rotativo = :orden')
        params['orden'] = int(payload['orden_rotativo'])
    if 'sede_id' in payload:
        fields.append('sede_id = :sede_id')
        params['sede_id'] = int(payload['sede_id'])
    if 'activo' in payload:
        fields.append('activo = :activo')
        params['activo'] = payload['activo']

    if not fields:
        return HttpResponseBadRequest('Nada que actualizar')

    params['guardia'] = guardia_id
    sql = f"UPDATE guardias SET {', '.join(fields)} WHERE guardia_id = :guardia"
    with connection.cursor() as cur:
        cur.execute(sql, params)
    return JsonResponse({'status': 'ok', 'guardia_id': guardia_id})


@csrf_exempt
@require_http_methods(["POST"])
def guardia_reactivar(request):
    try:
        payload = json.loads(request.body.decode())
        guardia_id = int(payload['guardia_id'])
    except Exception as e:
        return HttpResponseBadRequest(f'JSON inválido: {e}')
    with connection.cursor() as cur:
        cur.execute("UPDATE guardias SET activo = 'S' WHERE guardia_id = :id", {'id': guardia_id})
    return JsonResponse({'status': 'ok', 'guardia_id': guardia_id})


# ======================
# JORNADAS
# ======================
@require_http_methods(["GET"])
def jornadas_list(request):
        rows = _query("""
                SELECT jornada_id, nombre,
                       EXTRACT(HOUR FROM hora_ini_ref) AS hora_ini_h,
                       EXTRACT(MINUTE FROM hora_ini_ref) AS hora_ini_m,
                       EXTRACT(HOUR FROM hora_fin_ref) AS hora_fin_h,
                       EXTRACT(MINUTE FROM hora_fin_ref) AS hora_fin_m
                FROM jornadas
                ORDER BY jornada_id
        """)
        return JsonResponse({'jornadas': rows})

@csrf_exempt
@require_http_methods(["POST"])
def cargar_jornadas_defecto(request):
        with connection.cursor() as cur:
                cur.execute("BEGIN pkg_guardias.cargar_jornadas_defecto; END;")
        return JsonResponse({'status': 'ok', 'message': 'Jornadas cargadas (si estaban vacías)'})


# ======================
# REPORTES: HORAS TRABAJADAS
# ======================
@require_http_methods(["GET"])
def reporte_horas(request):
        """
        Query params:
            desde=YYYY-MM-DD (obligatorio)
            hasta=YYYY-MM-DD (obligatorio)
            sede_id=<id>     (opcional)
            guardia_id=<id>  (opcional)
        """
        desde = request.GET.get('desde')
        hasta = request.GET.get('hasta')
        sede_id = request.GET.get('sede_id')
        guardia_id = request.GET.get('guardia_id')

        if not desde or not hasta:
                return HttpResponseBadRequest("Faltan parámetros 'desde' y 'hasta' (YYYY-MM-DD).")

        sql = """
        SELECT
            g.guardia_id,
            g.apellidos || ', ' || g.nombres AS guardia,
            s.nombre AS sede,
            TRUNC(t.inicio) AS fecha,
            SUM( (t.fin - t.inicio) * 24 ) AS horas
        FROM guardias g
        JOIN sedes s ON s.sede_id = g.sede_id
        JOIN turnos t ON t.guardia_id = g.guardia_id
        WHERE t.inicio >= TO_DATE(:desde,'YYYY-MM-DD')
            AND t.fin    <  TO_DATE(:hasta,'YYYY-MM-DD') + 1
            AND (:sede_id   IS NULL OR g.sede_id   = :sede_id)
            AND (:guardia_id IS NULL OR g.guardia_id = :guardia_id)
        GROUP BY g.guardia_id, g.apellidos, g.nombres, s.nombre, TRUNC(t.inicio)
        ORDER BY s.nombre, fecha, g.apellidos, g.nombres
        """
        rows = _query(sql, {'desde': desde, 'hasta': hasta, 'sede_id': sede_id, 'guardia_id': guardia_id})
        # Normaliza decimales a float
        for r in rows:
                if 'horas' in r and r['horas'] is not None:
                        r['horas'] = float(r['horas'])
        return JsonResponse({'desde': desde, 'hasta': hasta, 'rows': rows})

@require_http_methods(["GET"])
def reporte_horas_csv(request):
        desde = request.GET.get('desde')
        hasta = request.GET.get('hasta')
        sede_id = request.GET.get('sede_id')
        guardia_id = request.GET.get('guardia_id')
        if not desde or not hasta:
                return HttpResponseBadRequest("Faltan parámetros 'desde' y 'hasta' (YYYY-MM-DD).")

        sql = """
        SELECT
            s.nombre AS sede,
            g.guardia_id,
            g.apellidos || ', ' || g.nombres AS guardia,
            TO_CHAR(TRUNC(t.inicio),'YYYY-MM-DD') AS fecha,
            ROUND(SUM( (t.fin - t.inicio) * 24 ), 2) AS horas
        FROM guardias g
        JOIN sedes s ON s.sede_id = g.sede_id
        JOIN turnos t ON t.guardia_id = g.guardia_id
        WHERE t.inicio >= TO_DATE(:desde,'YYYY-MM-DD')
            AND t.fin    <  TO_DATE(:hasta,'YYYY-MM-DD') + 1
            AND (:sede_id   IS NULL OR g.sede_id   = :sede_id)
            AND (:guardia_id IS NULL OR g.guardia_id = :guardia_id)
        GROUP BY s.nombre, g.guardia_id, g.apellidos, g.nombres, TRUNC(t.inicio)
        ORDER BY s.nombre, TRUNC(t.inicio), g.apellidos, g.nombres
        """
        rows = _query(sql, {'desde': desde, 'hasta': hasta, 'sede_id': sede_id, 'guardia_id': guardia_id})

        # Construir CSV
        resp = HttpResponse(content_type='text/csv; charset=utf-8')
        resp['Content-Disposition'] = f'attachment; filename="reporte_horas_{desde}_a_{hasta}.csv"'
        w = csv.writer(resp)
        w.writerow(['Sede', 'Guardia ID', 'Guardia', 'Fecha', 'Horas'])
        for r in rows:
                w.writerow([r['sede'], r['guardia_id'], r['guardia'], r['fecha'], r['horas']])
        return resp


@require_http_methods(["GET"])
def reporte_horas_diarias(request):
        """
        Usa la vista vw_horas_por_guardia_dia para obtener desglose diario.
        Query params opcionales: sede, guardia_id, desde, hasta
        
        NOTA: Esta funcionalidad requiere que exista la vista VW_HORAS_POR_GUARDIA_DIA en Oracle.
        Si la vista no existe, retorna un error amigable.
        """
        sede = request.GET.get('sede')
        guardia_id = request.GET.get('guardia_id')
        desde = request.GET.get('desde')
        hasta = request.GET.get('hasta')

        sql = """
        SELECT guardia_id, apellidos, nombres, sede, fecha, horas
        FROM vw_horas_por_guardia_dia
        WHERE (:sede IS NULL OR UPPER(sede) LIKE '%%' || UPPER(:sede) || '%%')
          AND (:guardia_id IS NULL OR guardia_id = :guardia_id)
          AND (:desde IS NULL OR fecha >= TO_DATE(:desde, 'YYYY-MM-DD'))
          AND (:hasta IS NULL OR fecha <= TO_DATE(:hasta, 'YYYY-MM-DD'))
        ORDER BY sede, fecha DESC, apellidos, nombres
        """
        try:
                rows = _query(sql, {'sede': sede, 'guardia_id': guardia_id, 'desde': desde, 'hasta': hasta})
                # Normalizar decimales
                for r in rows:
                        if 'horas' in r and r['horas'] is not None:
                                r['horas'] = float(r['horas'])
                return JsonResponse({'rows': rows})
        except Exception as e:
                error_msg = str(e)
                if 'ORA-00942' in error_msg:
                        return JsonResponse({
                                'error': 'La vista VW_HORAS_POR_GUARDIA_DIA no existe en la base de datos. Por favor cree la vista primero.'
                        }, status=500)
                return JsonResponse({'error': error_msg}, status=500)


