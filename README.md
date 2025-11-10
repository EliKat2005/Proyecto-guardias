## Sistema de Gestión de Guardias

Aplicación Django conectada a Oracle para administrar guardias, sedes, rotaciones de 24 horas y reportes de horas trabajadas. Integra lógica de negocio en PL/SQL (paquete `pkg_guardias`) y una vista analítica `vw_horas_por_guardia_dia`.

> 📚 **NUEVO:** Ver [INDICE_DOCUMENTACION.md](./INDICE_DOCUMENTACION.md) para acceso rápido a toda la documentación, incluyendo guías de inicio rápido, ejemplos de uso y diagramas visuales.

### Características principales
- Generación de rotación de 24h por sede (`pkg_guardias.generar_rotacion`)
- **Agregar guardias a rotaciones activas** - Crea guardias nuevos y añádelos automáticamente a ciclos en ejecución
  - Opción para especificar hora exacta de integración
  - Ajuste automático de turnos vecinos
  - Configuración de duración personalizada de turnos
- **Modificar horas de turno en caliente** - Redistribuye turnos de guardias en ciclos activos
  - Modificar duración de turnos para todos los guardias del ciclo
  - Modificar solo turnos de un guardia específico manteniendo los demás
  - Redistribución automática equitativa de las 24 horas
- Eliminación de turno con ajuste automático de vecinos (`pkg_guardias.eliminar_turno_y_ajustar`)
- CRUD de Sedes (activar/desactivar, eliminación con verificación de dependencias)
- CRUD de Guardias (alta, baja con reglas de negocio, reactivación, edición)
- Catálogo Jornadas (carga automática por paquete o fallback)
- Reportes: horas agregadas y horas diarias (vista Oracle)
- Exportación CSV de horas trabajadas
- Registro de eventos del sistema (tabla `reporte_eventos`)
- Interfaz de tema claro/oscuro con persistencia
- Selección dinámica de ciclos existentes para consultas y eliminaciones

### Requisitos
- Python 3.13+
- Oracle Database (usuario con paquete `pkg_guardias` y tablas necesarias)
- Herramienta `uv` para gestionar entorno (ya presente en proyecto)

### Instalación / Ejecución
```bash
# Crear y activar entorno (si no existe)
uv sync  # instala dependencias del pyproject.toml

# Ejecutar servidor Django
uv run python manage.py runserver
```
Servidor disponible en: http://127.0.0.1:8000/

### Configuración Oracle
En `turnos_site/settings.py` se define la conexión Django → Oracle (ENGINE django.db.backends.oracle). Asegúrate de que:
1. El usuario tenga creado el paquete `pkg_guardias` con los procedimientos:
	 - `crear_sede`
	 - `alta_guardia`
	 - `baja_guardia`
	 - `generar_rotacion`
	 - `eliminar_turno_y_ajustar`
	 - `cargar_jornadas_defecto` (opcional, con o sin paréntesis)
2. Existe la vista analítica de horas diarias:
```sql
CREATE OR REPLACE VIEW vw_horas_por_guardia_dia AS
SELECT 
	g.guardia_id,
	g.apellidos,
	g.nombres,
	s.nombre AS sede,
	TRUNC(t.inicio) AS fecha,
	SUM((t.fin - t.inicio) * 24) AS horas
FROM turnos t
JOIN guardias g ON t.guardia_id = g.guardia_id
JOIN sedes s ON t.sede_id = s.sede_id
GROUP BY g.guardia_id, g.apellidos, g.nombres, s.nombre, TRUNC(t.inicio);
```

### Endpoints principales (API)
- `POST /api/rotacion/generar/` Genera rotación de 24h
- `POST /api/rotacion/agregar-guardia/` Agrega guardia a ciclo activo con opciones avanzadas:
  - `hora_inicio` (opcional): Hora específica de integración
  - `duracion_turnos_min` (opcional): Duración personalizada de turnos
- `POST /api/rotacion/modificar-horas/` Redistribuye horas de turno en ciclo activo:
  - Puede modificar todos los guardias o solo uno específico
  - Ajusta automáticamente la distribución manteniendo 24h totales
- `GET /api/turnos/<sede_id>/<ciclo>/` Lista turnos de un ciclo (fecha con `T` o `_`)
- `POST /api/turno/eliminar/<turno_id>/` Elimina turno y ajusta vecinos
- `GET /api/reportes/eventos/` Eventos recientes
- `GET /api/sedes/` / `POST /api/sedes/crear/` / `POST /api/sedes/<id>/editar/`
- `POST /api/sedes/<id>/eliminar/` Elimina una sede (409 si tiene guardias/turnos relacionados)
- `GET /api/guardias/` / `POST /api/guardias/alta/` / `POST /api/guardias/baja/`
- `POST /api/guardias/<id>/eliminar/` Elimina guardia (409 si tiene turnos)
- `GET /api/jornadas/` / `POST /api/jornadas/cargar_defecto/`
- `GET /api/reportes/horas/` / `GET /api/reportes/horas.csv`
- `GET /api/reportes/horas-diarias/` (usa vista Oracle)
- `POST /api/rotacion/eliminar/<sede_id>/<ciclo>/` Elimina todos los turnos de la rotación
- `GET /api/sedes/<id>/eliminar/info/` Preview dependencias (guardias, turnos)
- `GET /api/guardias/<id>/eliminar/info/` Preview dependencias (turnos)

### Manejo de errores Oracle
El frontend mapea códigos ORA para mostrar mensajes amigables:
`ORA-00942`, `ORA-01861`, `ORA-02290`, `ORA-06550`, `ORA-20010`, `ORA-20020`, `ORA-20030`, `ORA-20110`, `ORA-20120`.

### Fallback Jornadas
Si `pkg_guardias.cargar_jornadas_defecto` falla, el backend inserta 3 jornadas (Mañana, Tarde, Noche) usando `NUMTODSINTERVAL` sólo si la tabla está vacía.

### Próximos pasos sugeridos
- Añadir dashboard con métricas rápidas.
- Mejorar estilo visual (Bootstrap avanzado, gráficos).
- Agregar pruebas automatizadas para lógica crítica.
- Exportación PDF de reportes.
- Forzar eliminación lógica (soft delete) de sedes y guardias si se requiere histórico.

### Licencia
Uso académico.

