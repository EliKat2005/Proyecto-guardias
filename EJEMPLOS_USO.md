# Ejemplos de Uso - Nuevas Funcionalidades

## 1. Agregar Guardia a Rotación Activa

### Caso 1: Agregar guardia en huecos disponibles (automático)

**Interfaz Web (Página Guardias):**
1. Ir a la sección "Guardias"
2. Hacer clic en "Crear guardia"
3. Llenar el formulario con los datos del guardia
4. Marcar la casilla "Agregar automáticamente a una rotación activa"
5. Seleccionar el ciclo deseado
6. Hacer clic en "Crear"

**API:**
```bash
curl -X POST http://localhost:8000/api/rotacion/agregar-guardia/ \
  -H "Content-Type: application/json" \
  -d '{
    "guardia_id": 10,
    "sede_id": 1,
    "ciclo": "2025-11-10 08:00"
  }'
```

**Respuesta:**
```json
{
  "status": "ok",
  "guardia_id": 10,
  "sede_id": 1,
  "ciclo": "2025-11-10 08:00",
  "turnos_creados": 3,
  "message": "Se crearon 3 turno(s) para el guardia en el ciclo activo"
}
```

### Caso 2: Agregar guardia en hora específica con duración personalizada

**Interfaz Web:**
1. En la página "Guardias", buscar el guardia existente
2. Hacer clic en el botón "Agregar a rotación" (icono +)
3. Seleccionar el ciclo
4. Marcar "Especificar hora de inicio del turno"
5. Seleccionar la hora deseada (ej: 14:00)
6. Ajustar "Duración de cada turno" (ej: 180 minutos = 3 horas)
7. Hacer clic en "Agregar"

**API:**
```bash
curl -X POST http://localhost:8000/api/rotacion/agregar-guardia/ \
  -H "Content-Type: application/json" \
  -d '{
    "guardia_id": 10,
    "sede_id": 1,
    "ciclo": "2025-11-10 08:00",
    "hora_inicio": "2025-11-10 14:00",
    "duracion_turnos_min": 180
  }'
```

**Qué sucede:**
- El sistema busca el turno que está activo a las 14:00
- Divide ese turno en el punto especificado
- Inserta el nuevo guardia con turnos de 180 minutos
- Ajusta los turnos vecinos automáticamente

---

## 2. Modificar Horas de Turno en Ciclo Activo

### Caso 1: Redistribuir todos los turnos con nueva duración

**Escenario:** Tienes una rotación de 24h con turnos de 2 horas (120 min) pero quieres cambiarlos a 3 horas (180 min)

**Interfaz Web (Página Inicio):**
1. En la sección "Modificar horas de turno en ciclo activo"
2. Seleccionar la sede
3. Seleccionar el ciclo
4. Ingresar nueva duración: 180 minutos
5. Dejar "Guardia específico" en "-- Todos los guardias --"
6. Hacer clic en "Redistribuir turnos"
7. Confirmar la acción

**API:**
```bash
curl -X POST http://localhost:8000/api/rotacion/modificar-horas/ \
  -H "Content-Type: application/json" \
  -d '{
    "sede_id": 1,
    "ciclo": "2025-11-10 08:00",
    "nueva_duracion_min": 180
  }'
```

**Respuesta:**
```json
{
  "status": "ok",
  "sede_id": 1,
  "ciclo": "2025-11-10 08:00",
  "guardias_afectados": 4,
  "turnos_totales_creados": 8,
  "duracion_turno_min": 180,
  "distribucion": {
    "1": 2,
    "2": 2,
    "3": 2,
    "4": 2
  },
  "message": "Se redistribuyeron los turnos con duración de 180 minutos"
}
```

**Qué sucede:**
- Se eliminan TODOS los turnos del ciclo
- Se recalcula cuántos turnos de 180 min caben en 24h (8 turnos)
- Se distribuyen equitativamente entre los 4 guardias (2 turnos cada uno)
- Se crean los nuevos turnos de forma rotativa

### Caso 2: Modificar solo turnos de un guardia específico

**Escenario:** Un guardia necesita turnos más cortos por razones médicas, pero los demás mantienen sus horarios

**Interfaz Web:**
1. En "Modificar horas de turno en ciclo activo"
2. Seleccionar sede y ciclo
3. Ingresar nueva duración: 90 minutos
4. Seleccionar el guardia específico en el dropdown
5. Hacer clic en "Redistribuir turnos"

**API:**
```bash
curl -X POST http://localhost:8000/api/rotacion/modificar-horas/ \
  -H "Content-Type: application/json" \
  -d '{
    "sede_id": 1,
    "ciclo": "2025-11-10 08:00",
    "guardia_id": 5,
    "nueva_duracion_min": 90
  }'
```

**Respuesta:**
```json
{
  "status": "ok",
  "sede_id": 1,
  "ciclo": "2025-11-10 08:00",
  "guardia_id": 5,
  "turnos_creados": 4,
  "duracion_turno_min": 90,
  "message": "Se reconfiguraron los turnos del guardia con duración de 90 minutos"
}
```

**Qué sucede:**
- Solo se eliminan los turnos del guardia especificado
- Se calculan los huecos disponibles (donde estaban sus turnos)
- Se crean nuevos turnos de 90 min en esos huecos
- Los turnos de los demás guardias NO se modifican

---

## 3. Flujo Completo de Trabajo

### Ejemplo: Rotación de Emergencias

**Situación inicial:**
- Sede: Hospital Central
- 3 guardias activos
- Rotación de 24h con turnos de 2 horas (slot_minutos = 120)

**Paso 1: Generar rotación inicial**
```bash
POST /api/rotacion/generar/
{
  "sede_id": 1,
  "ciclo": "2025-11-15 00:00",
  "inicio": "2025-11-15 00:00"
}
```
Resultado: 12 turnos de 2h distribuidos entre 3 guardias (4 turnos cada uno)

**Paso 2: Llega un nuevo guardia a las 10:00**
```bash
# Primero crear el guardia
POST /api/guardias/alta/
{
  "sede_id": 1,
  "apellidos": "Pérez",
  "nombres": "Juan",
  "sueldo": 1500,
  "orden_rotativo": 4
}
# Respuesta: guardia_id = 15

# Agregar a rotación en curso a las 10:00
POST /api/rotacion/agregar-guardia/
{
  "guardia_id": 15,
  "sede_id": 1,
  "ciclo": "2025-11-15 00:00",
  "hora_inicio": "2025-11-15 10:00",
  "duracion_turnos_min": 120
}
```
Resultado: El guardia 15 se integra a las 10:00, dividiendo el turno existente

**Paso 3: Cambio de política - turnos de 3 horas**
```bash
POST /api/rotacion/modificar-horas/
{
  "sede_id": 1,
  "ciclo": "2025-11-15 00:00",
  "nueva_duracion_min": 180
}
```
Resultado: Todos los turnos se redistribuyen con duración de 3h (8 turnos en total, 2 por guardia)

**Paso 4: Un guardia requiere turnos especiales de 1.5h**
```bash
POST /api/rotacion/modificar-horas/
{
  "sede_id": 1,
  "ciclo": "2025-11-15 00:00",
  "guardia_id": 15,
  "nueva_duracion_min": 90
}
```
Resultado: Solo el guardia 15 tiene turnos de 90 min, los demás mantienen 180 min

---

## 4. Casos de Uso Avanzados

### Integración gradual de personal

**Escenario:** Contratas 2 guardias nuevos y quieres integrarlos paulatinamente

```python
# Guardia 1 entra a las 06:00 con turnos de 2h
POST /api/rotacion/agregar-guardia/
{
  "guardia_id": 20,
  "sede_id": 1,
  "ciclo": "2025-11-16 00:00",
  "hora_inicio": "2025-11-16 06:00",
  "duracion_turnos_min": 120
}

# Guardia 2 entra a las 18:00 con turnos de 3h
POST /api/rotacion/agregar-guardia/
{
  "guardia_id": 21,
  "sede_id": 1,
  "ciclo": "2025-11-16 00:00",
  "hora_inicio": "2025-11-16 18:00",
  "duracion_turnos_min": 180
}
```

### Optimización de rotación existente

**Escenario:** Después de análisis, decides que 2.5h es óptimo

```python
# Redistribuir toda la rotación
POST /api/rotacion/modificar-horas/
{
  "sede_id": 1,
  "ciclo": "2025-11-17 00:00",
  "nueva_duracion_min": 150  # 2.5 horas
}
```

---

## 5. Validaciones y Límites

### Duraciones permitidas
- Mínimo: 30 minutos
- Máximo: 480 minutos (8 horas)
- Recomendado: múltiplos de 30 para mejor distribución

### Restricciones
- No se puede agregar un guardia que ya tiene turnos en el ciclo
- La hora de inicio debe estar dentro del ciclo de 24h
- El guardia debe estar activo y pertenecer a la sede
- Debe existir una rotación activa antes de agregar guardias

### Errores comunes

**Error: "El guardia ya tiene turnos en este ciclo"**
- Solución: Primero eliminar los turnos existentes o usar modificar-horas

**Error: "No hay rotación activa en este ciclo"**
- Solución: Generar primero una rotación con `/api/rotacion/generar/`

**Error: "La hora de inicio debe estar dentro del ciclo de 24h"**
- Solución: Verificar que hora_inicio esté entre ciclo y ciclo+24h

---

## 6. Mejores Prácticas

1. **Planificación:** Generar rotación base antes de agregar guardias
2. **Pruebas:** Usar ciclos futuros para probar configuraciones
3. **Monitoreo:** Revisar eventos del sistema después de modificaciones
4. **Backup:** Exportar reportes antes de cambios masivos
5. **Comunicación:** Informar a guardias antes de redistribuir turnos

---

## Soporte

Para más información, consultar:
- `README.md` - Documentación general
- `guardias/views.py` - Implementación de endpoints
- `/api/reportes/eventos/` - Log de operaciones del sistema
