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
- Pantalla «El Libro de las Hojas» con Almanaque, resultado, informe del lote
  (cifras, tres gráficos, tabla A4), **Guardar** como HTML autocontenido y
  **Limpiar** con confirmación.
- Suite completa en verde: **128 tests** (`python -m pytest -q`).
- Demo publicada en Vercel y repositorio privado en GitHub.

## Dónde está todo

| Cosa | Valor |
|---|---|
| App en producción | https://el-libro-de-las-hojas.vercel.app |
| Repositorio | https://github.com/nagold86/el-libro-de-las-hojas (privado) |
| Proyecto Vercel | `gold-df31/el-libro-de-las-hojas` |
| Local | `python -m uvicorn app.main:app --host 127.0.0.1 --port 8765 --reload` |
| Almanaque local | `storage/` con 4 inspecciones de prueba |
| Respaldo del almanaque | `%TEMP%\fellowship-almanaque-backup` (12 archivos) |

## Condiciones de la demo (ADR-012)

- En Vercel el repositorio vive en `/tmp/fellowship-storage`: es **efímero**, se
  pierde al reiniciarse la instancia. El almacén de producción está vacío.
- Límite de subida en producción: 4 MB (`GET /api/config`); en local, 10 MB.
- La demo acredita contrato y método, no persistencia. Para historial real hay
  que apuntar `FELLOWSHIP_STORAGE_DIR` a un volumen o servicio externo.
- El repo no está conectado a Vercel: `git push` no publica. Republicar con
  `vercel --prod` (la CLI conviene instalarla global: `npm install -g vercel`).

## Orden de lectura antes de tocar nada

1. [`README.md`](../README.md) — qué es, cómo correrlo, contrato HTTP.
2. [`docs/DECISIONES.md`](DECISIONES.md) — ADRs, la más reciente arriba (hoy
   ADR-012 en Vercel, ADR-011 vaciado, ADR-010 informe, ADR-009 aislamiento).
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

- **Escape en el diálogo del informe**: en la ventana headless no cerró; el
  botón «Cerrar» sí. Falta confirmarlo en un navegador real antes de tocar
  código, porque el `<dialog>` nativo ya lo resuelve.
- Ingesta con manifest y hashes en `data/`; conjunto golden de lesiones para
  medir IoU; validación por lote de Boromir.
- Si la demo deja de ser demo: storage persistente y conexión del repo con
  Vercel para publicación automática.

## Cómo empezar la próxima sesión

Decir el objetivo y el alcance en el primer mensaje, por ejemplo:

> «Nuevo proyecto dentro de Fellowship: <objetivo>. Es este repo; leé
> `docs/TRASPASO.md` y `docs/DECISIONES.md` antes de proponer nada.»

Si el proyecto nuevo es otro repositorio o aplicación, conviene además un
workspace distinto para no arrastrar este dataset ni esta configuración.
