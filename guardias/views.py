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

@require_http_methods(["GET"])
def sedes_ciclos(request, sede_id):
        """Lista los ciclos (fechas) distintos existentes para una sede, ordenados desc."""
        sql = """
        SELECT TO_CHAR(cf, 'YYYY-MM-DD HH24:MI') AS ciclo
        FROM (
            SELECT DISTINCT ciclo_fecha AS cf
            FROM turnos
            WHERE sede_id = :sede
        )
        ORDER BY cf DESC
        """
        rows = _query(sql, {'sede': sede_id})
        ciclos = [r['ciclo'] for r in rows]
        return JsonResponse({'sede_id': sede_id, 'ciclos': ciclos})

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
def sede_eliminar(request, sede_id):
    """
    Elimina una sede por ID. Respuestas:
      - 200: eliminado
      - 404: no existe
      - 409: conflicto por integridad referencial (FK hijas)
      - 500: otro error
    """
    try:
        with connection.cursor() as cur:
            cur.execute("DELETE FROM sedes WHERE sede_id = :sede", {'sede': sede_id})
            if cur.rowcount == 0:
                return JsonResponse({'error': 'Sede no encontrada'}, status=404)
        return JsonResponse({'status': 'ok', 'sede_id': sede_id})
    except Exception as e:
        msg = str(e)
        # ORA-02292: integrity constraint violated - child record found
        if 'ORA-02292' in msg or 'integrity constraint' in msg.lower():
            return JsonResponse({'error': 'No se puede eliminar la sede porque tiene registros relacionados (guardias/turnos).'}, status=409)
        return JsonResponse({'error': msg}, status=500)

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
# ELIMINACIÓN: GUARDIA, ROTACIÓN, PREVIEWS
# ======================
@csrf_exempt
@require_http_methods(["POST"])
def guardia_eliminar(request, guardia_id):
    """
    Elimina una guardia por ID. Retorna 200 si elimina, 404 si no existe,
    409 si hay turnos relacionados.
    """
    try:
        with connection.cursor() as cur:
            cur.execute("DELETE FROM guardias WHERE guardia_id = :id", {'id': guardia_id})
            if cur.rowcount == 0:
                return JsonResponse({'error': 'Guardia no encontrada'}, status=404)
        return JsonResponse({'status': 'ok', 'guardia_id': guardia_id})
    except Exception as e:
        msg = str(e)
        if 'ORA-02292' in msg or 'integrity constraint' in msg.lower():
            return JsonResponse({'error': 'No se puede eliminar: existen turnos asociados a esta guardia.'}, status=409)
        return JsonResponse({'error': msg}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def rotacion_eliminar(request, sede_id, ciclo):
    """
    Elimina todos los turnos de una rotación (ciclo) para una sede dada.
    ciclo puede venir como 'YYYY-MM-DD_HH:MI' o 'YYYY-MM-DDTHH:MI'.
    """
    ciclo_dt = ciclo.replace('_', ' ').replace('T', ' ')
    try:
        with connection.cursor() as cur:
            cur.execute(
                """
                DELETE FROM turnos
                WHERE sede_id = :sede
                  AND ciclo_fecha = TO_DATE(:ciclo, 'YYYY-MM-DD HH24:MI')
                """,
                {'sede': sede_id, 'ciclo': ciclo_dt}
            )
            borrados = cur.rowcount or 0
        return JsonResponse({'status': 'ok', 'eliminados': int(borrados), 'sede_id': sede_id, 'ciclo': ciclo_dt})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@csrf_exempt
@require_http_methods(["POST"])
def rotacion_agregar_guardia(request):
    """
    Agrega un guardia a una rotación existente, generando turnos automáticamente.
    Body JSON: {
        "guardia_id": 10,
        "sede_id": 1,
        "ciclo": "2025-11-10 08:00",
        "hora_inicio": "2025-11-10 14:00",  # opcional - hora específica de integración
        "duracion_turnos_min": 120  # opcional - duración deseada de cada turno en minutos
    }
    
    Estrategia mejorada:
    1. Validar que el guardia pertenece a la sede y está activo
    2. Si se especifica hora_inicio, insertar al guardia en ese momento ajustando turnos vecinos
    3. Si no se especifica, buscar huecos en el ciclo
    4. Redistribuir equitativamente las horas entre todos los guardias
    """
    try:
        data = json.loads(request.body)
        guardia_id = int(data.get('guardia_id'))
        sede_id = int(data.get('sede_id'))
        ciclo = data.get('ciclo', '')
        ciclo_dt = ciclo.replace('_', ' ').replace('T', ' ')
        hora_inicio = data.get('hora_inicio')  # opcional
        duracion_turnos_min = data.get('duracion_turnos_min')  # opcional
        
        from datetime import datetime, timedelta
        
        with connection.cursor() as cur:
            # 1. Validar guardia
            cur.execute("""
                SELECT g.guardia_id, g.activo, s.slot_minutos, s.nombre
                FROM guardias g
                JOIN sedes s ON s.sede_id = g.sede_id
                WHERE g.guardia_id = :gid AND g.sede_id = :sid
            """, {'gid': guardia_id, 'sid': sede_id})
            row = cur.fetchone()
            if not row:
                return JsonResponse({'error': 'Guardia no encontrado o no pertenece a la sede'}, status=404)
            if row[1] != 'S':
                return JsonResponse({'error': 'El guardia no está activo'}, status=400)
            
            slot_min = duracion_turnos_min or row[2] or 120
            sede_nombre = row[3]
            
            # 2. Verificar si ya tiene turnos en este ciclo
            cur.execute("""
                SELECT COUNT(*) FROM turnos
                WHERE guardia_id = :gid
                  AND sede_id = :sid
                  AND ciclo_fecha = TO_DATE(:ciclo, 'YYYY-MM-DD HH24:MI')
            """, {'gid': guardia_id, 'sid': sede_id, 'ciclo': ciclo_dt})
            ya_tiene = cur.fetchone()[0]
            if ya_tiene > 0:
                return JsonResponse({'error': 'El guardia ya tiene turnos en este ciclo'}, status=400)
            
            # 3. Obtener turnos existentes del ciclo (ordenados por inicio)
            cur.execute("""
                SELECT turno_id, guardia_id,
                       inicio, fin,
                       ROUND((fin - inicio) * 24 * 60) AS duracion_min
                FROM turnos
                WHERE sede_id = :sid
                  AND ciclo_fecha = TO_DATE(:ciclo, 'YYYY-MM-DD HH24:MI')
                ORDER BY inicio
            """, {'sid': sede_id, 'ciclo': ciclo_dt})
            turnos_existentes = cur.fetchall()
            
            if not turnos_existentes:
                return JsonResponse({'error': 'No hay rotación activa en este ciclo. Genere primero una rotación.'}, status=400)
            
            ciclo_inicio = datetime.strptime(ciclo_dt, '%Y-%m-%d %H:%M')
            ciclo_fin = ciclo_inicio + timedelta(hours=24)
            
            # Obtener jornada por defecto
            cur.execute("SELECT jornada_id FROM jornadas WHERE ROWNUM = 1")
            jornada_row = cur.fetchone()
            jornada_id = jornada_row[0] if jornada_row else None
            
            turnos_creados = 0
            
            # CASO 1: Se especificó hora_inicio - insertar en momento específico ajustando vecinos
            if hora_inicio:
                hora_inicio_dt = hora_inicio.replace('_', ' ').replace('T', ' ')
                momento_insercion = datetime.strptime(hora_inicio_dt, '%Y-%m-%d %H:%M')
                
                # Validar que la hora está dentro del ciclo
                if momento_insercion < ciclo_inicio or momento_insercion >= ciclo_fin:
                    return JsonResponse({'error': 'La hora de inicio debe estar dentro del ciclo de 24h'}, status=400)
                
                # Encontrar el turno que contiene este momento
                turno_a_dividir = None
                for t in turnos_existentes:
                    if t[2] <= momento_insercion < t[3]:
                        turno_a_dividir = t
                        break
                
                if not turno_a_dividir:
                    return JsonResponse({'error': 'No hay ningún turno en ese momento para ajustar'}, status=400)
                
                # Dividir el turno existente
                turno_id_orig = turno_a_dividir[0]
                guardia_id_orig = turno_a_dividir[1]
                inicio_orig = turno_a_dividir[2]
                fin_orig = turno_a_dividir[3]
                
                # Calcular fin del nuevo turno (usar slot_min)
                fin_nuevo_turno = momento_insercion + timedelta(minutes=slot_min)
                if fin_nuevo_turno > fin_orig:
                    fin_nuevo_turno = fin_orig
                
                # Actualizar turno original para que termine cuando empieza el nuevo
                cur.execute("""
                    UPDATE turnos 
                    SET fin = :nuevo_fin
                    WHERE turno_id = :tid
                """, {'nuevo_fin': momento_insercion, 'tid': turno_id_orig})
                
                # Insertar nuevo turno
                cur.execute("""
                    INSERT INTO turnos (sede_id, ciclo_fecha, guardia_id, inicio, fin, jornada_id)
                    VALUES (:sede, TO_DATE(:ciclo, 'YYYY-MM-DD HH24:MI'), :guardia, :inicio, :fin, :jornada)
                """, {
                    'sede': sede_id,
                    'ciclo': ciclo_dt,
                    'guardia': guardia_id,
                    'inicio': momento_insercion,
                    'fin': fin_nuevo_turno,
                    'jornada': jornada_id
                })
                turnos_creados += 1
                
                # Si queda espacio después del nuevo turno, crear otro turno para el guardia original
                if fin_nuevo_turno < fin_orig:
                    duracion_restante = (fin_orig - fin_nuevo_turno).total_seconds() / 60
                    if duracion_restante >= 30:  # Mínimo 30 minutos
                        cur.execute("""
                            INSERT INTO turnos (sede_id, ciclo_fecha, guardia_id, inicio, fin, jornada_id)
                            VALUES (:sede, TO_DATE(:ciclo, 'YYYY-MM-DD HH24:MI'), :guardia, :inicio, :fin, :jornada)
                        """, {
                            'sede': sede_id,
                            'ciclo': ciclo_dt,
                            'guardia': guardia_id_orig,
                            'inicio': fin_nuevo_turno,
                            'fin': fin_orig,
                            'jornada': jornada_id
                        })
                
            # CASO 2: No se especificó hora - buscar huecos y distribuir equitativamente
            else:
                # Calcular guardias únicos y duración promedio
                guardias_unicos = len(set(t[1] for t in turnos_existentes))
                total_min = sum(t[4] for t in turnos_existentes)
                
                # Con el nuevo guardia, recalcular distribución
                guardias_unicos += 1
                duracion_promedio_por_guardia = 1440 / guardias_unicos  # 24h = 1440 min
                num_turnos_nuevos = max(1, int(duracion_promedio_por_guardia / slot_min))
                
                # Buscar huecos
                intervalos_ocupados = [(t[2], t[3]) for t in turnos_existentes]
                intervalos_ocupados.sort()
                
                huecos = []
                t_actual = ciclo_inicio
                for ini, fin in intervalos_ocupados:
                    if t_actual < ini:
                        huecos.append((t_actual, ini))
                    t_actual = max(t_actual, fin)
                if t_actual < ciclo_fin:
                    huecos.append((t_actual, ciclo_fin))
                
                # Ordenar huecos por tamaño
                huecos.sort(key=lambda h: (h[1] - h[0]), reverse=True)
                
                # Crear turnos en los huecos
                duracion_slot = timedelta(minutes=slot_min)
                for hueco_ini, hueco_fin in huecos:
                    if turnos_creados >= num_turnos_nuevos:
                        break
                    
                    hueco_duracion = (hueco_fin - hueco_ini).total_seconds() / 60
                    turnos_en_hueco = int(hueco_duracion / slot_min)
                    
                    t_inicio = hueco_ini
                    for _ in range(min(turnos_en_hueco, num_turnos_nuevos - turnos_creados)):
                        t_fin = t_inicio + duracion_slot
                        if t_fin > hueco_fin:
                            break
                        
                        cur.execute("""
                            INSERT INTO turnos (sede_id, ciclo_fecha, guardia_id, inicio, fin, jornada_id)
                            VALUES (:sede, TO_DATE(:ciclo, 'YYYY-MM-DD HH24:MI'), :guardia, :inicio, :fin, :jornada)
                        """, {
                            'sede': sede_id,
                            'ciclo': ciclo_dt,
                            'guardia': guardia_id,
                            'inicio': t_inicio,
                            'fin': t_fin,
                            'jornada': jornada_id
                        })
                        turnos_creados += 1
                        t_inicio = t_fin
            
        return JsonResponse({
            'status': 'ok',
            'guardia_id': guardia_id,
            'sede_id': sede_id,
            'ciclo': ciclo_dt,
            'turnos_creados': turnos_creados,
            'message': f'Se crearon {turnos_creados} turno(s) para el guardia en el ciclo activo'
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'JSON inválido'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def rotacion_modificar_horas(request):
    """
    Modifica las horas de turno de todos los guardias en un ciclo activo,
    redistribuyendo equitativamente el tiempo de 24 horas.
    
    Body JSON: {
        "sede_id": 1,
        "ciclo": "2025-11-10 08:00",
        "nueva_duracion_min": 180  # nueva duración en minutos para cada turno
    }
    
    O para modificar un guardia específico:
    {
        "sede_id": 1,
        "ciclo": "2025-11-10 08:00",
        "guardia_id": 5,
        "nueva_duracion_min": 240
    }
    
    La función:
    1. Calcula cuántos turnos debe tener cada guardia con la nueva duración
    2. Elimina los turnos actuales del ciclo (o del guardia específico)
    3. Regenera los turnos con la nueva distribución
    """
    try:
        data = json.loads(request.body)
        sede_id = int(data.get('sede_id'))
        ciclo = data.get('ciclo', '')
        ciclo_dt = ciclo.replace('_', ' ').replace('T', ' ')
        nueva_duracion_min = int(data.get('nueva_duracion_min', 120))
        guardia_id_especifico = data.get('guardia_id')  # opcional
        
        if nueva_duracion_min < 30 or nueva_duracion_min > 1440:
            return JsonResponse({'error': 'La duración debe estar entre 30 y 1440 minutos (24h)'}, status=400)
        
        from datetime import datetime, timedelta
        ciclo_inicio = datetime.strptime(ciclo_dt, '%Y-%m-%d %H:%M')
        ciclo_fin = ciclo_inicio + timedelta(hours=24)
        
        with connection.cursor() as cur:
            # Verificar que existe el ciclo
            cur.execute("""
                SELECT COUNT(*) FROM turnos
                WHERE sede_id = :sid AND ciclo_fecha = TO_DATE(:ciclo, 'YYYY-MM-DD HH24:MI')
            """, {'sid': sede_id, 'ciclo': ciclo_dt})
            
            if cur.fetchone()[0] == 0:
                return JsonResponse({'error': 'No existe rotación en este ciclo'}, status=404)
            
            # Obtener jornada por defecto
            cur.execute("SELECT jornada_id FROM jornadas WHERE ROWNUM = 1")
            jornada_row = cur.fetchone()
            jornada_id = jornada_row[0] if jornada_row else None
            
            # Decidir el flujo según si es guardia específico o todos
            if guardia_id_especifico:
                # Verificar si el guardia tiene turnos en este ciclo
                cur.execute("""
                    SELECT COUNT(*) FROM turnos
                    WHERE sede_id = :sid 
                      AND ciclo_fecha = TO_DATE(:ciclo, 'YYYY-MM-DD HH24:MI')
                      AND guardia_id = :gid
                """, {'sid': sede_id, 'ciclo': ciclo_dt, 'gid': int(guardia_id_especifico)})
                
                tiene_turnos = cur.fetchone()[0] > 0
                
                if not tiene_turnos:
                    # El guardia NO está en el ciclo - AGREGAR turnos en huecos
                    # Verificar que el guardia existe y está activo
                    cur.execute("""
                        SELECT g.guardia_id, g.activo
                        FROM guardias g
                        WHERE g.guardia_id = :gid AND g.sede_id = :sid
                    """, {'gid': int(guardia_id_especifico), 'sid': sede_id})
                    
                    guardia_row = cur.fetchone()
                    if not guardia_row:
                        return JsonResponse({'error': 'El guardia no existe o no pertenece a esta sede'}, status=404)
                    if guardia_row[1] != 'S':
                        return JsonResponse({'error': 'El guardia no está activo'}, status=400)
                    
                    # Obtener huecos disponibles
                    cur.execute("""
                        SELECT inicio, fin
                        FROM turnos
                        WHERE sede_id = :sid 
                          AND ciclo_fecha = TO_DATE(:ciclo, 'YYYY-MM-DD HH24:MI')
                        ORDER BY inicio
                    """, {'sid': sede_id, 'ciclo': ciclo_dt})
                    
                    turnos_existentes = cur.fetchall()
                    
                    # Encontrar huecos
                    huecos = []
                    t_actual = ciclo_inicio
                    for ini, fin in turnos_existentes:
                        if t_actual < ini:
                            huecos.append((t_actual, ini))
                        t_actual = max(t_actual, fin)
                    if t_actual < ciclo_fin:
                        huecos.append((t_actual, ciclo_fin))
                    
                    if not huecos:
                        return JsonResponse({'error': 'No hay espacio disponible en el ciclo para agregar turnos'}, status=400)
                    
                    # Ordenar huecos por tamaño
                    huecos.sort(key=lambda h: (h[1] - h[0]), reverse=True)
                    
                    # Calcular cuántos turnos se pueden crear
                    tiempo_disponible = sum((h[1] - h[0]).total_seconds() / 60 for h in huecos)
                    num_turnos_guardia = max(1, int(tiempo_disponible / nueva_duracion_min))
                    
                    # Crear turnos en los huecos
                    turnos_creados = 0
                    for hueco_ini, hueco_fin in huecos:
                        if turnos_creados >= num_turnos_guardia:
                            break
                        
                        hueco_duracion = (hueco_fin - hueco_ini).total_seconds() / 60
                        turnos_en_hueco = int(hueco_duracion / nueva_duracion_min)
                        
                        t_inicio = hueco_ini
                        for _ in range(min(turnos_en_hueco, num_turnos_guardia - turnos_creados)):
                            t_fin = min(t_inicio + timedelta(minutes=nueva_duracion_min), hueco_fin)
                            
                            cur.execute("""
                                INSERT INTO turnos (sede_id, ciclo_fecha, guardia_id, inicio, fin, jornada_id)
                                VALUES (:sede, TO_DATE(:ciclo, 'YYYY-MM-DD HH24:MI'), :guardia, :inicio, :fin, :jornada)
                            """, {
                                'sede': sede_id,
                                'ciclo': ciclo_dt,
                                'guardia': int(guardia_id_especifico),
                                'inicio': t_inicio,
                                'fin': t_fin,
                                'jornada': jornada_id
                            })
                            turnos_creados += 1
                            t_inicio = t_fin
                    
                    return JsonResponse({
                        'status': 'ok',
                        'sede_id': sede_id,
                        'ciclo': ciclo_dt,
                        'guardia_id': int(guardia_id_especifico),
                        'turnos_creados': turnos_creados,
                        'duracion_turno_min': nueva_duracion_min,
                        'message': f'Guardia agregado al ciclo con {turnos_creados} turno(s) de {nueva_duracion_min} minutos'
                    })
                
                # El guardia SÍ tiene turnos - modificar los existentes
                # Eliminar turnos existentes del guardia
                cur.execute("""
                    DELETE FROM turnos
                    WHERE sede_id = :sid 
                      AND ciclo_fecha = TO_DATE(:ciclo, 'YYYY-MM-DD HH24:MI')
                      AND guardia_id = :gid
                """, {'sid': sede_id, 'ciclo': ciclo_dt, 'gid': int(guardia_id_especifico)})
                
                # Para un guardia específico, calcular cuántos turnos necesita
                # basado en su proporción del tiempo total
                minutos_totales = 1440  # 24 horas
                
                # Obtener tiempo ocupado por otros guardias
                cur.execute("""
                    SELECT SUM((fin - inicio) * 24 * 60) FROM turnos
                    WHERE sede_id = :sid 
                      AND ciclo_fecha = TO_DATE(:ciclo, 'YYYY-MM-DD HH24:MI')
                      AND guardia_id != :gid
                """, {'sid': sede_id, 'ciclo': ciclo_dt, 'gid': int(guardia_id_especifico)})
                
                minutos_otros = cur.fetchone()[0] or 0
                minutos_disponibles = max(0, minutos_totales - minutos_otros)
                num_turnos_guardia = max(1, int(minutos_disponibles / nueva_duracion_min))
                
                # Obtener huecos disponibles
                cur.execute("""
                    SELECT inicio, fin
                    FROM turnos
                    WHERE sede_id = :sid 
                      AND ciclo_fecha = TO_DATE(:ciclo, 'YYYY-MM-DD HH24:MI')
                    ORDER BY inicio
                """, {'sid': sede_id, 'ciclo': ciclo_dt})
                
                turnos_existentes = cur.fetchall()
                
                # Encontrar huecos
                huecos = []
                t_actual = ciclo_inicio
                for ini, fin in turnos_existentes:
                    if t_actual < ini:
                        huecos.append((t_actual, ini))
                    t_actual = max(t_actual, fin)
                if t_actual < ciclo_fin:
                    huecos.append((t_actual, ciclo_fin))
                
                # Ordenar huecos por tamaño
                huecos.sort(key=lambda h: (h[1] - h[0]), reverse=True)
                
                # Crear turnos en los huecos
                turnos_creados = 0
                for hueco_ini, hueco_fin in huecos:
                    if turnos_creados >= num_turnos_guardia:
                        break
                    
                    hueco_duracion = (hueco_fin - hueco_ini).total_seconds() / 60
                    turnos_en_hueco = int(hueco_duracion / nueva_duracion_min)
                    
                    t_inicio = hueco_ini
                    for _ in range(min(turnos_en_hueco, num_turnos_guardia - turnos_creados)):
                        t_fin = min(t_inicio + timedelta(minutes=nueva_duracion_min), hueco_fin)
                        
                        cur.execute("""
                            INSERT INTO turnos (sede_id, ciclo_fecha, guardia_id, inicio, fin, jornada_id)
                            VALUES (:sede, TO_DATE(:ciclo, 'YYYY-MM-DD HH24:MI'), :guardia, :inicio, :fin, :jornada)
                        """, {
                            'sede': sede_id,
                            'ciclo': ciclo_dt,
                            'guardia': int(guardia_id_especifico),
                            'inicio': t_inicio,
                            'fin': t_fin,
                            'jornada': jornada_id
                        })
                        turnos_creados += 1
                        t_inicio = t_fin
                
                return JsonResponse({
                    'status': 'ok',
                    'sede_id': sede_id,
                    'ciclo': ciclo_dt,
                    'guardia_id': int(guardia_id_especifico),
                    'turnos_creados': turnos_creados,
                    'duracion_turno_min': nueva_duracion_min,
                    'message': f'Se reconfiguraron los turnos del guardia con duración de {nueva_duracion_min} minutos'
                })
            
            else:
                # Redistribuir equitativamente entre todos los guardias del ciclo
                # Obtener guardias únicos del ciclo
                cur.execute("""
                    SELECT DISTINCT guardia_id FROM turnos
                    WHERE sede_id = :sid AND ciclo_fecha = TO_DATE(:ciclo, 'YYYY-MM-DD HH24:MI')
                    ORDER BY guardia_id
                """, {'sid': sede_id, 'ciclo': ciclo_dt})
                
                guardias_a_procesar = [row[0] for row in cur.fetchall()]
                
                if not guardias_a_procesar:
                    return JsonResponse({'error': 'No hay guardias en este ciclo'}, status=400)
                
                num_guardias = len(guardias_a_procesar)
                
                # Eliminar todos los turnos existentes para redistribuir
                cur.execute("""
                    DELETE FROM turnos
                    WHERE sede_id = :sid AND ciclo_fecha = TO_DATE(:ciclo, 'YYYY-MM-DD HH24:MI')
                """, {'sid': sede_id, 'ciclo': ciclo_dt})
                
                # Redistribuir equitativamente
                turnos_por_guardia = {}
                tiempo_actual = ciclo_inicio
                guardia_idx = 0
                turnos_totales_creados = 0
                
                while tiempo_actual < ciclo_fin:
                    guardia_id = guardias_a_procesar[guardia_idx]
                    
                    # Calcular fin del turno
                    fin_turno = tiempo_actual + timedelta(minutes=nueva_duracion_min)
                    if fin_turno > ciclo_fin:
                        fin_turno = ciclo_fin
                    
                    # Insertar turno
                    cur.execute("""
                        INSERT INTO turnos (sede_id, ciclo_fecha, guardia_id, inicio, fin, jornada_id)
                        VALUES (:sede, TO_DATE(:ciclo, 'YYYY-MM-DD HH24:MI'), :guardia, :inicio, :fin, :jornada)
                    """, {
                        'sede': sede_id,
                        'ciclo': ciclo_dt,
                        'guardia': guardia_id,
                        'inicio': tiempo_actual,
                        'fin': fin_turno,
                        'jornada': jornada_id
                    })
                    
                    if guardia_id not in turnos_por_guardia:
                        turnos_por_guardia[guardia_id] = 0
                    turnos_por_guardia[guardia_id] += 1
                    turnos_totales_creados += 1
                    
                    tiempo_actual = fin_turno
                    guardia_idx = (guardia_idx + 1) % num_guardias
                
                return JsonResponse({
                    'status': 'ok',
                    'sede_id': sede_id,
                    'ciclo': ciclo_dt,
                    'guardias_afectados': num_guardias,
                    'turnos_totales_creados': turnos_totales_creados,
                    'duracion_turno_min': nueva_duracion_min,
                    'distribucion': turnos_por_guardia,
                    'message': f'Se redistribuyeron los turnos con duración de {nueva_duracion_min} minutos'
                })
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'JSON inválido'}, status=400)
    except ValueError as e:
        return JsonResponse({'error': f'Valor inválido: {str(e)}'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@require_http_methods(["GET"])
def sede_eliminar_info(request, sede_id):
    """Devuelve contadores de dependencias que impedirían borrar una sede."""
    try:
        with connection.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM guardias WHERE sede_id = :s", {'s': sede_id})
            guardias_count = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM turnos WHERE sede_id = :s", {'s': sede_id})
            turnos_count = cur.fetchone()[0]
        return JsonResponse({'sede_id': sede_id, 'guardias': int(guardias_count), 'turnos': int(turnos_count)})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@require_http_methods(["GET"])
def guardia_eliminar_info(request, guardia_id):
    """Devuelve contadores de dependencias para una guardia (turnos)."""
    try:
        with connection.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM turnos WHERE guardia_id = :g", {'g': guardia_id})
            turnos_count = cur.fetchone()[0]
        return JsonResponse({'guardia_id': guardia_id, 'turnos': int(turnos_count)})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


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
    """
    Intenta cargar jornadas por defecto usando el paquete PL/SQL.
    Si falla (por nombre/firma del procedimiento), aplica un fallback
    que inserta las 3 jornadas base si la tabla está vacía.
    """
    try:
        with connection.cursor() as cur:
            # Intento 1: llamar al procedimiento del paquete (con y sin paréntesis)
            try:
                cur.execute("BEGIN pkg_guardias.cargar_jornadas_defecto(); END;")
                return JsonResponse({'status': 'ok', 'message': 'Jornadas cargadas vía paquete PL/SQL'})
            except Exception:
                # Segundo intento sin paréntesis (por si la firma es PROCEDURE sin parámetros explícitos)
                cur.execute("BEGIN pkg_guardias.cargar_jornadas_defecto; END;")
                return JsonResponse({'status': 'ok', 'message': 'Jornadas cargadas vía paquete PL/SQL'})
    except Exception as pkg_err:
        # Fallback: insertar jornadas si la tabla está vacía
        try:
            plsql = """
            DECLARE
              v_count NUMBER;
            BEGIN
              SELECT COUNT(*) INTO v_count FROM jornadas;
              IF v_count = 0 THEN
                INSERT INTO jornadas (nombre, hora_ini_ref, hora_fin_ref)
                VALUES ('Mañana', NUMTODSINTERVAL(8,'HOUR'), NUMTODSINTERVAL(16,'HOUR'));
                INSERT INTO jornadas (nombre, hora_ini_ref, hora_fin_ref)
                VALUES ('Tarde',  NUMTODSINTERVAL(16,'HOUR'), NUMTODSINTERVAL(24,'HOUR'));
                INSERT INTO jornadas (nombre, hora_ini_ref, hora_fin_ref)
                VALUES ('Noche',  NUMTODSINTERVAL(0,'HOUR'),  NUMTODSINTERVAL(8,'HOUR'));
              END IF;
            END;
            """
            with connection.cursor() as cur:
                cur.execute(plsql)
            return JsonResponse({'status': 'ok', 'message': 'Jornadas cargadas por fallback (tabla estaba vacía)'})
        except Exception as fb_err:
            return JsonResponse({'error': f'No fue posible cargar jornadas por defecto. Paquete error: {pkg_err}; Fallback error: {fb_err}'}, status=500)


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


