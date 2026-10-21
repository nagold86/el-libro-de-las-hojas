# Validación

Registro de veredictos de Boromir, uno por lote auditado. Los umbrales vigentes y
su justificación viven en [`DECISIONES.md`](DECISIONES.md); acá solo se registra
qué se midió, con qué n y qué se decidió.

Formato de cada entrada:

```md
## <fecha> — <lote>
- n: <hojas>, variantes incluidas: <sí/no y por qué>
- IoU lesión: medio <x>, peor <x> (<hoja>)
- Repetibilidad: diferencia máxima <x> %
- Fuga de datos: <ninguna | detalle>
- Fallos: <hoja, etapa, motivo>
- Veredicto: APTO | NO APTO
```

---

## 2026-10-21 — cierre del MVP: vaciar el almanaque y copia del informe

- n: 4 inspecciones reales en `storage/` durante la prueba de navegador.
- Endpoint: `DELETE /api/inspections` → `204`; con el almacén vacío también
  `204`. `tests/test_repository.py` y `tests/test_contract.py` cubren artefactos,
  `.gitkeep`, listado vacío y `404` por id; suite completa: 125 tests en verde.
- Limpiar: con 4 inspecciones el botón está habilitado; el diálogo dice
  «¿Vaciar el almanaque?» y «Se eliminarán las 4 inspecciones…». Cancelar no
  envía ningún `DELETE` y conserva las 4. Confirmar produce `204`, deja «sin
  inspecciones», oculta el resultado y deshabilita el botón.
- Guardar: desde el informe con 4 imágenes, `showSaveFilePicker` existe pero el
  diálogo nativo no es alcanzable en la ventana headless (AbortError, la app no
  muestra error); con la API suprimida, la descarga produce
  `informe-lote-2026-10-21.html` de 75.193 bytes, 0 `<button>`, 7 SVG, 2 bloques
  `<style>` y 0 referencias `/media/`; se abre sin el servidor con tablas,
  gráficos y CSS de impresión.
- Informe verificado: 4 imágenes, 141 lesiones, mediana 10,92 %, peor 17,62 %.
- Consola y red: sin errores JS; `/api/health`, `/api/config`,
  `/api/inspections`, `/api/reports/lot` y `/media` responden 200/204.
- Repetibilidad: los 125 tests pasan; la copia se genera desde el DOM, no vuelve
  a pedir el informe.
- Fuga de datos: ninguna; las capturas y el HTML quedaron en Descargas, fuera
  del repositorio.
- Fallos: el diálogo nativo de guardado no se pudo operar en headless; queda
  verificado el respaldo de descarga, no el selector del sistema. El `close` del
  `<dialog>` no disparó en esa ventana oculta; despachado a mano, se ejecutó el
  mismo manejador. Es una limitación del entorno, no del código.
- Veredicto: APTO para cerrar el MVP; la elección de carpeta con el selector
  nativo queda para una prueba manual en escritorio.

---

## 2026-10-21 — pipeline completo con aislamiento e informe del lote

- n: 210 hojas originales, una por hoja; variantes excluidas para no inflar `n`.
- Resultado: 183/210 aceptadas (87,1 %); 27 rechazadas con `UnusableImage`
  (borrosa, una también con `poca_superficie_valida`) por la nitidez medida
  sobre el interior erosionado de la máscara válida. Las 183 aceptadas usan
  `primer_plano`: el aislamiento no recortó ninguna hoja del dataset.
- Compuerta de dominio: 210/210 aceptadas en la pasada dedicada; en el
  subconjunto aceptado por el pipeline, `score = 0` en 180 y `score = 1` en 3.
- Advertencias: `poca_superficie_valida` en 10 hojas aceptadas; sin otros flags.
- Externas USDA: `k5992-1` recorte 2752×1800 → 1136×1380, hoja 60,0 %, 94
  lesiones / 4,97 %; `k5992_hoja` 880×1085 sin recorte efectivo, 99 / 6,22 %;
  `k5992_parche` primer plano 508×508, 72 / 8,73 %; `k5993-1` recorte 2738×1800
  → 2039×1800 con `varias_regiones_verdes`, 63 / 38,43 %.
- Informe: 5 registros (4 externas + 1 legado sin aislamiento) → 342 lesiones,
  mediana de área 8,73 %, peor 38,43 %, dominante severo, conteos 0/1/2/2
  (0/20/40/40 %); métodos `desconocido` 1, `grabcut` 3, `primer_plano` 1.
- UI: Edge headless con CDP, 4 barras de histograma, 5 puntos de dispersión, 5
  barras de ranking y 5 filas de tabla; sin errores de consola ni pedidos
  fallidos. A 390×844 la tabla se lee como fichas. Impresión: PDF A4 de 4
  páginas legible, con pilas tipográficas estáticas porque los tipos variables
  de Google se exportan como Type 3 y pierden métricas.
- IoU de lesión: pendiente de conjunto golden; esta entrada no lo declara.
- Repetibilidad: determinista; GrabCut con `cv2.setRNGSeed(0)` y mismas
  entradas producen el mismo recorte y las mismas cifras.
- Fuga de datos: ninguna; las externas viven en `sandbox/externas/` y no entran
  a `imgs/` ni al manifest.
- Fallos: 27 hojas del dataset rechazadas por borrosas (19 con la métrica
  anterior); no se verificó si son falsos rechazos. `k5993-1` conserva varias
  regiones verdes y mide sobre una escena amplia.
- Veredicto: APTO para aislamiento e informe; reserva declarada de calidad por
  los 27/210 rechazos. No sustituye la auditoría de IoU.

---

## 2026-10-21 — compuerta de dominio, segunda pasada (imagen original)

- n: 210 hojas originales, una por hoja; variantes excluidas para no inflar `n`.
- Resultado: 210/210 aceptadas (0 % de falsos rechazos); 206 con `score = 0` y
  4 con `score = 1`: tres por matiz verde (46,7 %, 23,1 %, 48,9 %) y una por
  entropía (5,45 bits), todas dentro de la tolerancia de una violación.
- Controles negativos: documento 6 violaciones, pared 5, cielo 4, ruido 4;
  4/4 rechazados.
- Prueba externa (USDA ARS, dominio público): primer plano de hoja con lesiones
  de TMV aceptado con `score = 0`; recorte con hoja y mano aceptado con
  `score = 0`, pero el overlay mancha la mano y la pared; dos escenas completas
  rechazadas (verde 20,7 % y 41,2 %; matiz 20,1 % y 40,9 %).
- Fallo encontrado y corregido: la compuerta medía la imagen balanceada; un
  primer plano verde puro bajaba de 97,9 % a 22,7 % de superficie verde y se
  rechazaba. Ahora mide la imagen original y del preproceso solo usa la máscara
  (ADR-008, enmienda).
- Repetibilidad: determinista; mismas entradas, mismo `score` y mismos motivos.
- Fuga de datos: ninguna; las fotos externas viven en `sandbox/externas/` y no
  entran al dataset.
- Veredicto: APTO. Sustituye la pasada anterior, calibrada sobre imagen
  balanceada.

---

## 2026-10-21 — compuerta de dominio (primera pasada, histórica)

- n: 210 hojas originales, una por hoja; variantes excluidas para no inflar `n`.
- Resultado: 210/210 aceptadas; `score = 0` en las 210 (0 % de falsos rechazos).
- Controles negativos: documento 6 violaciones, pared 5, cielo 4, ruido 2;
  4/4 rechazados.
- Fallos: ninguna hoja del dataset. La calibración inicial, más estricta en
  color, rechazaba 2 hojas enfermas (`IMG_20231015_111151_13`,
  `IMG_20231015_111757_15`); se relajaron los umbrales de color y la barrera
  quedó en textura y entropía (ADR-008).
- Nota: esta pasada medía la imagen balanceada; la sustituye la segunda pasada.
- Repetibilidad: compuerta determinista; mismas entradas, mismo `score` y
  mismos motivos.
- Fuga de datos: ninguna; se usó una imagen por hoja.
- Veredicto: APTO para `envelope_v1`. No audita IoU de lesión: la segmentación
  sigue pendiente de conjunto golden.

---

## 2026-10-21 — línea base (histórica)

- n: 0 hojas (sin corridas todavía).
- Estado: el pipeline no está implementado. No hay veredicto.
- Umbrales pendientes: IoU mínimo de lesión, error máximo de área relativa,
  exigencia de repetibilidad. Se fijan en el ADR de la primera corrida.
- Recordatorio: `imgs/` tiene 210 hojas y 2000 archivos. El `n` se declara en
  hojas, nunca en archivos.
- Nota: esta entrada describe el estado previo a la implementación; el pipeline
  quedó completo y verificado en las entradas siguientes.
