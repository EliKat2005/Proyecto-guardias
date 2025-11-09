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
    # ciclo: 'YYYY-MM-DD_HH:MI' → 'YYYY-MM-DD HH:MI'
    ciclo_dt = ciclo.replace('_', ' ')
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
    try:
        payload = json.loads(request.body.decode())
        sede_id = int(payload['sede_id'])
        ciclo   = payload['ciclo']   # 'YYYY-MM-DD HH24:MI'
        inicio  = payload['inicio']  # 'YYYY-MM-DD HH24:MI'
    except Exception as e:
        return HttpResponseBadRequest(f'JSON inválido: {e}')
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
        cur.execute(plsql, {'sede': sede_id, 'ciclo': ciclo, 'inicio': inicio})
    return JsonResponse({'status': 'ok', 'message': 'Rotación generada'})

@csrf_exempt
@require_http_methods(["POST"])
def eliminar_turno(request, turno_id):
    plsql = "BEGIN pkg_guardias.eliminar_turno_y_ajustar(:turno); END;"
    with connection.cursor() as cur:
        cur.execute(plsql, {'turno': turno_id})
    return JsonResponse({'status': 'ok', 'message': f'Turno {turno_id} eliminado y vecinos ajustados'})

@require_http_methods(["GET"])
def eventos(request):
    data = _query("""
      SELECT reporte_id, tipo_evento,
             TO_CHAR(fecha_evento,'YYYY-MM-DD HH24:MI:SS') AS fecha_evento,
             sede_id, guardia_id, turno_id,
             SUBSTR(detalle,1,160) AS detalle
      FROM reporte_eventos
      ORDER BY fecha_evento DESC
    """)
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


# ======================
# JORNADAS
# ======================
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


