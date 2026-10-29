# Traspaso — estado al cierre de la sesión del MVP

Pase de estado para arrancar la próxima sesión sin depender del historial de la
conversación. Si algo de acá contradice al código, manda el código; si contradice
a un ADR, se actualiza el ADR.

## Qué está terminado

- Pipeline clásico de punta a punta: aislamiento de hoja, preproceso, calidad,
  compuerta de dominio, segmentación de lesiones y nervaduras, morfometría,
  descriptores y overlay.
- API contract-first con `inspections`, informe agregado `GET /api/reports/lot`,
  borrado por id y vaciado total `DELETE /api/inspections`.
- Registro de análisis en Postgres detrás de la interfaz `InspectionStore`
  (ADR-016): con `DATABASE_URL` el almanaque sobrevive al reinicio; sin ella, el
  almacén de archivos sigue siendo el camino por defecto. El overlay y las 17
  capas se regeneran bajo demanda.
- Login con usuarios en la base y sesión firmada (ADR-017): `scrypt` con sal por
  usuario, cookie `HttpOnly` + HMAC-SHA256, roles `admin` y `operador`, guardas
  sobre todo salvo `/api/health`, `/api/config` y `/api/auth/*`. Sin base no hay
  puerta: la demo en archivos sigue abierta.
- Historial con filtros (`q`, `version`, `owner`, `since`, `until`) y paginación
  `limit`/`offset`; cada hoja guarda quién la subió y con qué versión del software,
  y `GET /api/versions` resume cuántas midió cada una.
- Alcance por dueño y conserjería (ADR-018): el `operador` ve, abre, descarga,
  informa y vacía solo sus hojas —lo ajeno responde `404`—, y el `admin` ve el
  almanaque completo. Diálogo **Usuarios** con alta y baja de cuentas, y
  «Borrar hojas sin dueño» (`DELETE /api/inspections?unassigned=true`) para las
  que quedan tras dar de baja a alguien.
- Pantalla «El Libro de las Hojas» con puerta de entrada, Almanaque con filtros y
  «Cargar más hojas», resultado, informe del lote (cifras, tres gráficos, tabla
  A4), **Guardar** como HTML autocontenido y **Limpiar** con confirmación.
- Suite completa en verde: **282 tests** (44,2 s) contra `fellowship_test`; los de
  Postgres se saltean solos si no hay servidor (`python -m pytest`).
- Demo publicada en Vercel y repositorio privado en GitHub.

## Dónde está todo

| Cosa | Valor |
|---|---|
| App en producción | https://el-libro-de-las-hojas.vercel.app |
| Repositorio | https://github.com/nagold86/el-libro-de-las-hojas (privado) |
| Proyecto Vercel | `gold-df31/el-libro-de-las-hojas` |
| Local | `python -m uvicorn app.main:app --host 127.0.0.1 --port 8765 --reload` |
| Base local | `postgresql://fellowship:fellowship@127.0.0.1:5433/fellowship` (puerto 5433, `docker compose up -d`) |
| Tests de base | `fellowship_test` en el mismo servidor (`FELLOWSHIP_TEST_DATABASE_URL`) |
| Almanaque local | `storage/` con 4 inspecciones de prueba |
| Respaldo del almanaque | `%TEMP%\fellowship-almanaque-backup` (12 archivos) |

## Condiciones de la demo (ADR-012)

- En Vercel el repositorio vive en `/tmp/fellowship-storage`: es **efímero**, se
  pierde al reiniciarse la instancia. El almacén de producción está vacío.
- Límite de subida en producción: 4 MB (`GET /api/config`); en local, 10 MB.
- La demo acredita contrato y método, no persistencia. Para historial real
  alcanza con apuntar `DATABASE_URL` a un Postgres (ADR-016), sin tocar código; en
  ese momento la app pasa a pedir login (ADR-017) y el administrador inicial sale
  de `FELLOWSHIP_ADMIN_USER` / `FELLOWSHIP_ADMIN_PASSWORD`.
- El repo no está conectado a Vercel: `git push` no publica. Republicar con
  `vercel --prod` (la CLI conviene instalarla global: `npm install -g vercel`).

## Orden de lectura antes de tocar nada

1. [`README.md`](../README.md) — qué es, cómo correrlo, mapa de carpetas y contrato HTTP.
2. [`docs/DECISIONES.md`](DECISIONES.md) — ADRs, la más reciente arriba (hoy
   ADR-018 alcance por dueño, ADR-017 login y versiones, ADR-016 Postgres, ADR-015
   clorosis, ADR-014 histéresis, ADR-013 dos vistas, ADR-012 Vercel).
3. [`fellowship/PIPELINE.md`](../fellowship/PIPELINE.md) — recorrido del pedido,
   módulo por módulo, y las reglas que no se negocian.
4. [`docs/VALIDACION.md`](VALIDACION.md) — qué se midió y con qué `n`.
5. [`docs/DESIGN.md`](DESIGN.md) — sistema visual y comportamiento de la pantalla.

## Reglas que siguen vigentes

- Solo visión clásica: OpenCV, NumPy y SciPy. Nada de modelos preentrenados.
- `core/` no importa FastAPI ni `app/`; la API solo valida, delega y persiste.
- Toda decisión que cambie contrato, método o rutas necesita un ADR nuevo.
- La UI y la documentación van en español; la estética es «La Ventana Redonda».
- `imgs/`, `storage/`, `sandbox/` y `.vercel-tmp/` no se commitean.

## Pendientes conocidos

- **Máscaras del conjunto dorado sin corregir.** Hay 38 candidatas generadas por
  el detector en `data/golden/masks/` y ninguna corregida por una persona. Hasta
  que no se corrijan con `sandbox/anotar.py`, el puntaje mide movimiento del
  detector, no acierto. Empezar por las 16 de calibración y dejar las 22 de test
  para validar. De las 51 hojas, 13 nunca podrán llevar máscara: el filtro de
  nitidez las rechaza.
- **Clorosis: decidir si se resta.** Hoy se reporta al lado del área afectada.
  Restarla del área de lesión es una decisión de producto, no de método, y
  necesita el conjunto dorado corregido para no empeorar el reporte.
- **Deuda de método**: los dos parámetros nuevos de la histéresis (fracción 0,5 y
  tope de 8 px) están razonados pero no barridos contra máscaras humanas; el tope
  de píxeles depende de la escala de la imagen, no del tamaño de la lesión; y
  `min_sharpness` sigue calibrado sobre la vista de presentación.
- **Escape en el diálogo del informe**: en la ventana headless no cerró; el
  botón «Cerrar» sí. Falta confirmarlo en un navegador real antes de tocar
  código, porque el `<dialog>` nativo ya lo resuelve.
- **Sin integración continua**: los 282 tests corren solo a mano.
- **Camino de base verificado** (2026-10-29): migraciones desde cero que
  sobreviven al proceso, login, filtros del historial y una hoja que reaparece
  con su original después de reiniciar el servidor. Falta la prueba equivalente
  contra un DSN gestionado (Neon), que es lo único que cambia en producción.
- **La puerta y la conserjería no se probaron en navegador.** La API está
  verificada de punta a punta y el JS pasa `node --check`, pero el diálogo de
  login, los filtros, el sello de versión, el diálogo **Usuarios** y las
  confirmaciones solo se miraron en código.
- **Sin base, un DSN mal configurado da 500.** Con `DATABASE_URL` apuntando a un
  servidor caído, `/api/health` lo dice (`sin conexión`) pero las rutas de
  `inspections` fallan con `DatabaseUnavailable` sin traducir a `503`. Faltan un
  handler y un ADR.
- **El almanaque actual no se migra solo.** Los registros que ya están en
  `storage/` se pueden importar con un script que reutilice el mismo `id`; no es
  parte de la entrega.
- **Vaciado total sin guarda.** `DELETE /api/inspections` vacía el archivo —todo
  si quien pide es `admin`, solo lo propio si es `operador` (ADR-018)— y ahora que
  el histórico persiste eso es más caro que antes: conviene exigir
  `X-Confirm-Clear` o `FELLOWSHIP_ALLOW_CLEAR=false` en producción (cambia
  contrato, necesita ADR). En la pantalla, «Limpiar» se deshabilita mientras hay
  un filtro puesto.
- **Cuentas sin auditoría ni cambio de clave desde la pantalla.** La baja borra la
  fila y deja las hojas sin dueño; no queda registro más allá del log del servidor.
  El cambio de clave existe en la API (`POST /api/auth/password`) pero no tiene
  formulario, y no hay reactivación de cuentas dadas de baja.
- **Deduplicación por `image_sha256`.** La columna ya existe y está indexada;
  falta decidir si una hoja repetida se cuenta dos veces en el informe.
- **Agregación en SQL** cuando el lote crezca: el informe sigue trayendo todo a
  Python, aunque el historial ya filtra por `q`, `version`, `owner`, `since` y
  `until`. Faltan filtros por severidad y por `method_version` en la pantalla (las
  columnas tienen índice).
- Si la demo deja de ser demo: DSN gestionado (Neon/Supabase) y conexión del repo
  con Vercel para publicación automática.

## Cómo empezar la próxima sesión

Decir el objetivo y el alcance en el primer mensaje, por ejemplo:

> «Nuevo proyecto dentro de Fellowship: <objetivo>. Es este repo; leé
> `docs/TRASPASO.md` y `docs/DECISIONES.md` antes de proponer nada.»

Si el proyecto nuevo es otro repositorio o aplicación, conviene además un
workspace distinto para no arrastrar este dataset ni esta configuración.
