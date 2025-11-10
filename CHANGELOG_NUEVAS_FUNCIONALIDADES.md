# Changelog - Nuevas Funcionalidades de Gestión Dinámica de Turnos

## Fecha: 10 de noviembre de 2025

---

## 🎯 Resumen de Cambios

Se implementaron dos funcionalidades principales solicitadas:

1. **Agregar guardias a rotaciones activas con opciones avanzadas**
2. **Modificar horas de turno en ciclos activos (en caliente)**

---

## 📋 Funcionalidades Implementadas

### 1. Agregar Guardia a Rotación Activa (Mejorado)

**Endpoint:** `POST /api/rotacion/agregar-guardia/`

**Características:**
- ✅ Agregar guardia en huecos automáticos (comportamiento original)
- ✅ **NUEVO:** Especificar hora exacta de integración
- ✅ **NUEVO:** Configurar duración personalizada de turnos
- ✅ Ajuste automático de turnos vecinos
- ✅ Validaciones completas de integridad

**Parámetros del endpoint:**
```json
{
  "guardia_id": 10,           // Requerido
  "sede_id": 1,               // Requerido
  "ciclo": "2025-11-10 08:00", // Requerido
  "hora_inicio": "2025-11-10 14:00",  // NUEVO - Opcional
  "duracion_turnos_min": 180  // NUEVO - Opcional (default: slot_minutos)
}
```

**Casos de uso:**
- Integración automática en huecos disponibles
- Integración en momento específico (ej: cuando llega el guardia)
- División de turnos existentes para hacer espacio
- Personalización de duración por necesidades especiales

---

### 2. Modificar Horas de Turno en Ciclo Activo

**Endpoint:** `POST /api/rotacion/modificar-horas/`

**Características:**
- ✅ Redistribuir TODOS los turnos con nueva duración
- ✅ Modificar solo turnos de un guardia específico
- ✅ Mantenimiento automático de 24h totales
- ✅ Distribución equitativa entre guardias
- ✅ Preservación de turnos de otros guardias (modo individual)

**Parámetros del endpoint:**
```json
{
  "sede_id": 1,               // Requerido
  "ciclo": "2025-11-10 08:00", // Requerido
  "nueva_duracion_min": 180,   // Requerido (30-480)
  "guardia_id": 5              // Opcional - si se omite, afecta a todos
}
```

**Casos de uso:**
- Cambio de política de turnos (ej: de 2h a 3h)
- Ajuste para un guardia con necesidades especiales
- Optimización de distribución de carga
- Reconfiguración dinámica sin recrear rotación

---

## 🔧 Cambios Técnicos

### Backend (Python/Django)

**Archivo:** `guardias/views.py`

1. **Función `rotacion_agregar_guardia()` - Mejorada**
   - Agregada lógica para hora_inicio específica
   - División inteligente de turnos existentes
   - Soporte para duracion_turnos_min personalizada
   - Mejor manejo de huecos y distribución

2. **Función `rotacion_modificar_horas()` - NUEVA**
   - Redistribución global de turnos
   - Modo individual por guardia
   - Cálculo automático de distribución equitativa
   - Validaciones de rango (30-480 min)

**Archivo:** `guardias/urls.py`
- Agregada ruta: `path('rotacion/modificar-horas/', views.rotacion_modificar_horas)`

---

### Frontend (HTML/JavaScript)

**Archivo:** `templates/guardias.html`

**Mejoras en modal de creación de guardias:**
- Sección de opciones avanzadas (desplegable)
- Checkbox para especificar hora de inicio
- Input datetime-local para hora específica
- Input numérico para duración de turnos
- Validaciones visuales

**Mejoras en botón "Agregar a rotación":**
- Modal con opciones avanzadas
- Configuración de hora de inicio
- Configuración de duración
- Feedback visual mejorado

**Archivo:** `templates/home.html`

**Nuevo formulario:**
- Sección "Modificar horas de turno en ciclo activo"
- Selector de sede y ciclo
- Input de nueva duración (30-480 min)
- Selector opcional de guardia específico
- Carga dinámica de guardias del ciclo
- Confirmaciones de seguridad

**JavaScript agregado:**
- Función `cargarGuardiasSede()` - Carga guardias de una sede
- Función `cargarGuardiasCiclo()` - Carga guardias de un ciclo específico
- Handler `form-mod-horas` - Procesa redistribución
- Validaciones de rangos y confirmaciones

---

## 📚 Documentación

**Archivos actualizados:**

1. **README.md**
   - Actualizada sección de características principales
   - Documentados nuevos endpoints
   - Agregadas opciones de parámetros

2. **EJEMPLOS_USO.md** (NUEVO)
   - Ejemplos completos de cada funcionalidad
   - Casos de uso del mundo real
   - Ejemplos de API con curl
   - Mejores prácticas
   - Solución de problemas comunes

3. **CHANGELOG_NUEVAS_FUNCIONALIDADES.md** (Este archivo)
   - Resumen completo de cambios
   - Especificaciones técnicas
   - Flujos de trabajo

---

## 🎨 Mejoras de UX/UI

### Interfaz de Guardias
- Opciones avanzadas en acordeón/colapsable
- Hints contextuales (tooltips)
- Validación en tiempo real
- Feedback visual inmediato

### Interfaz Principal
- Nueva sección claramente identificada
- Íconos descriptivos (🕐 ⚡ ↻)
- Mensajes de confirmación antes de acciones destructivas
- Indicadores de progreso

### Mensajes de Usuario
- Mensajes de éxito con conteo de turnos
- Errores amigables con sugerencias
- Advertencias antes de modificaciones masivas

---

## 🔐 Validaciones y Seguridad

### Validaciones Backend
- ✅ Guardia debe pertenecer a la sede
- ✅ Guardia debe estar activo
- ✅ No duplicar turnos en mismo ciclo
- ✅ Hora de inicio dentro del ciclo de 24h
- ✅ Duración entre 30-480 minutos
- ✅ Ciclo debe existir antes de agregar

### Validaciones Frontend
- ✅ Campos requeridos
- ✅ Rangos numéricos (min/max)
- ✅ Formatos de fecha/hora válidos
- ✅ Confirmaciones para cambios masivos

---

## 🚀 Flujos de Trabajo Soportados

### Flujo 1: Guardia Nuevo en Hora Específica
```
1. Usuario crea guardia en formulario
2. Marca "Agregar a rotación"
3. Marca "Especificar hora de inicio"
4. Selecciona hora (ej: 14:00)
5. Configura duración (ej: 180 min)
6. Sistema inserta guardia en ese momento
7. Turnos vecinos se ajustan automáticamente
```

### Flujo 2: Cambio de Política de Turnos
```
1. Usuario va a página Inicio
2. Selecciona sede y ciclo activo
3. Ingresa nueva duración (ej: 150 min)
4. Deja "todos los guardias" seleccionado
5. Confirma acción
6. Sistema redistribuye toda la rotación
7. Todos obtienen turnos de 150 min equitativamente
```

### Flujo 3: Ajuste Individual
```
1. Usuario identifica guardia que necesita cambio
2. Selecciona sede, ciclo y guardia específico
3. Ingresa nueva duración (ej: 90 min)
4. Confirma acción
5. Solo ese guardia recibe turnos de 90 min
6. Demás guardias mantienen sus turnos
```

---

## 📊 Ejemplos de Respuestas

### Agregar Guardia con Hora Específica
```json
{
  "status": "ok",
  "guardia_id": 15,
  "sede_id": 1,
  "ciclo": "2025-11-10 08:00",
  "turnos_creados": 2,
  "message": "Se crearon 2 turno(s) para el guardia en el ciclo activo"
}
```

### Redistribuir Todos los Turnos
```json
{
  "status": "ok",
  "sede_id": 1,
  "ciclo": "2025-11-10 08:00",
  "guardias_afectados": 4,
  "turnos_totales_creados": 8,
  "duracion_turno_min": 180,
  "distribucion": {"1": 2, "2": 2, "3": 2, "4": 2},
  "message": "Se redistribuyeron los turnos con duración de 180 minutos"
}
```

### Modificar Solo Un Guardia
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

---

## 🐛 Errores Conocidos y Soluciones

### Error: "El guardia ya tiene turnos en este ciclo"
**Causa:** Intentar agregar un guardia que ya está en la rotación  
**Solución:** Usar `modificar-horas` con guardia_id específico

### Error: "No hay rotación activa"
**Causa:** Intentar modificar un ciclo que no existe  
**Solución:** Generar rotación primero con `/api/rotacion/generar/`

### Error: "La duración debe estar entre 30 y 480 minutos"
**Causa:** Valor fuera de rango  
**Solución:** Ajustar a 0.5h - 8h (30-480 min)

---

## 🔮 Posibles Mejoras Futuras

1. **Plantillas de Configuración**
   - Guardar configuraciones favoritas de duración
   - Aplicar plantillas a múltiples ciclos

2. **Vista Previa**
   - Mostrar cómo quedaría la redistribución antes de aplicar
   - Comparación lado a lado: antes/después

3. **Restricciones Personalizadas**
   - Límite de horas consecutivas por guardia
   - Tiempos de descanso obligatorios
   - Preferencias de horario por guardia

4. **Optimización Automática**
   - Sugerir duración óptima basada en guardias disponibles
   - Detección de distribuciones desbalanceadas

5. **Historial de Cambios**
   - Registro detallado de modificaciones
   - Capacidad de revertir cambios (rollback)

---

## 🧪 Pruebas Sugeridas

### Prueba 1: Agregar en Hora Específica
1. Crear rotación con 3 guardias
2. Agregar cuarto guardia a las 12:00
3. Verificar que turno de las 12:00 se dividió correctamente

### Prueba 2: Redistribuir Todo
1. Rotación existente con turnos de 120 min
2. Cambiar a 180 min
3. Verificar que suma total sigue siendo 24h

### Prueba 3: Modificar Individual
1. Rotación con 4 guardias
2. Cambiar solo guardia #2 a 90 min
3. Verificar que guardias #1, #3, #4 no cambiaron

---

## 📞 Soporte

Para preguntas o reportar problemas:
- Revisar `EJEMPLOS_USO.md` para casos de uso
- Consultar `/api/reportes/eventos/` para logs del sistema
- Verificar validaciones en `guardias/views.py`

---

## ✅ Checklist de Implementación

- [x] Endpoint `rotacion_agregar_guardia` mejorado
- [x] Endpoint `rotacion_modificar_horas` creado
- [x] Rutas agregadas en `urls.py`
- [x] UI mejorada en `guardias.html`
- [x] Formulario nuevo en `home.html`
- [x] Validaciones backend completas
- [x] Validaciones frontend completas
- [x] Documentación README actualizada
- [x] Ejemplos de uso documentados
- [x] Changelog creado
- [x] Mensajes de error amigables
- [x] Confirmaciones de seguridad
- [x] Feedback visual implementado

---

**Versión:** 1.1.0  
**Autor:** Sistema de Guardias - Mejoras Dinámicas  
**Fecha:** 10/11/2025
