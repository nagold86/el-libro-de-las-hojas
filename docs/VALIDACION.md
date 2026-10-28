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

## 2026-10-28 — clorosis por ángulo de matiz (ADR-015)

- n: calibración del puntaje sobre 31 hojas sanas más 2 controles (clorótica y
  necrosis); de punta a punta, 63 hojas analizables de las primeras 80 por hoja
  física (las mismas 17 fuera de política por nitidez). `sandbox/auditar.py`.
- Separación del criterio: mediana del ángulo **0,646** en hojas sanas; por encima
  de 0,85 queda **0,3 %** de superficie en la hoja mediana, p90 3,0 %, máximo
  21,3 % (una hoja con necrosis severa, no una sana). La control clorótica da
  **0,906** de mediana y 64,6 % de su superficie sobre el umbral.
- Extensión medida: clorosis mediana **0,0275 %** de la superficie, p90 3,94 %,
  máximo (control) **57,98 %**. La hoja clorótica queda con 72,99 % de área
  afectada y la clorosis explica 58 de esos puntos.
- Solape con la máscara parda: mediana **100 %**. La clorosis no agrega área, la
  etiqueta: por eso el reporte la muestra al lado del área afectada y no sumada.
- Riesgo vigilado (hojas sanas marcadas): 3 hojas por encima del 10 % (10,70 %,
  29,36 %, 29,28 %), y las tres ya venían con **≥ 17 %** de área parda reportada.
  No apareció ninguna hoja limpia marcada.
- Repetibilidad: dos inspecciones de la misma hoja dan la misma máscara
  (sha256 idéntico) y la misma área; 0,5798 en la control, 0,00055 en
  `110914_14`, 0,02282 en `110302_8`. La traza pasa a **17 capas**.
- Costo: **≈ 0,37 s por hoja** en el pipeline completo (una pasada, sin las dos
  ramas de la auditoría; dos corridas dieron 360 y 381 ms).
- Fuga de datos: el umbral 0,85 se eligió mirando hojas del mismo dataset
  (incluida la control), así que **no es un valor validado en un conjunto
  separado**. Está declarado en el ADR y en `PipelineSettings`.
- Fallos: ninguna excepción nueva; las 17 hojas siguen fuera por nitidez
  (`min_sharpness = 15`).
- Veredicto: **APTO con condiciones**. (1) La clorosis no cambia el área
  reportada como lesión: decidir si debe restarse es una decisión pendiente, no
  un efecto de este cambio. (2) Falta la máscara humana del conjunto dorado para
  hablar de exactitud; hoy todo lo medido es coherencia interna.

---

## 2026-10-28 — histéresis de dos umbrales (ADR-014)

- n: 63 hojas analizables de las primeras 80 por hoja física (17 quedaron fuera de
  política por nitidez, sharpness 5,8–12,9 contra `min_sharpness = 15`); mismo
  pipeline dos veces por hoja, histéresis apagada y encendida. Más 38 archivos del
  conjunto dorado puntuados contra máscaras prellenadas.
- IoU de lesión: **no declarado como exactitud**. `golden.py score` da IoU medio
  **0,750** (peor 0,189), Dice 0,845, precisión 0,618, recall 1,000, pero la
  referencia son las máscaras que prellenó el detector previo: el recall 1,000 es
  una identidad (el crecimiento expande, nunca quita) y el IoU mide desplazamiento,
  no acierto. Ninguna de las 38 máscaras está corregida por una persona todavía.
- Extensión: área mediana **0,36 % → 0,60 %** (factor 1,35×; p90 2,16×; máximo
  5,29× en una hoja de 0,02 %). Sigue 0,27× del techo de la vista con balance
  (2,21 %): no se volvió al sobre-marcado de ADR-012 y anteriores.
- Contención: componentes 348 → 348 sobre las 63 hojas, máximo por hoja 37 → 37,
  **0 hojas con más componentes** y 9 hojas sin lesión antes y después. El
  crecimiento no puede inventar una mancha porque todo pixel agregado está
  conectado a una semilla.
- Umbral bajo: p50 sano mediano **−0,143**, umbral bajo mediano **−0,071**; el piso
  de −0,15 no se alcanzó en ninguna hoja. Caso degenerado: la hoja clorótica
  `IMG_20231015_111757_15` tiene p50 positivo, los dos umbrales coinciden y no
  crece nada (77,97 % → 78,13 %, p50 +0,053).
- Repetibilidad: dos corridas sobre `IMG_20231015_110914_14` dan máscara idéntica,
  área 0,007529, 4 componentes, 15 capas y 15 imágenes iguales pixel a pixel.
  Umbral bajo −0,0668 con p50 sano −0,1336; 2 601 px agregados.
- Casos: `IMG_20231015_110914_14` 4 componentes / 0,32 % → 4 / 0,75 % (vuelve el
  halo del ampollado, la nervadura central sigue fuera); `IMG_20231015_111721_8`
  2 / 0,39 % → 2 / 0,59 % (los pliegues en sombra siguen fuera).
- Fuga de datos: ninguna. Las máscaras prellenadas salen del mismo pipeline que se
  evalúa, por eso se informan como `auto` en `_provenance.json` y no se declaran
  como referencia.
- Fallos declarados: el techo de 8 px es un parámetro de escala —a 1100 px de lado
  máximo— y no se adapta al tamaño de la mancha; con manchas de diámetro menor a
  ~16 px el halo puede quedar afuera. La histéresis tampoco separa clorosis de
  necrosis.
- Veredicto: **APTO** para la contención y la reversibilidad (componentes, hojas
  sin lesión y caso degenerado se comportan como se declaró). **NO APTO** para
  declarar mejor segmentación: falta que una persona corrija las 38 máscaras y que
  el IoU se mida contra esa referencia.

---

## 2026-10-28 — vista de análisis canónica (ADR-013)

- n: 210 hojas, una por hoja; variantes colapsadas por nombre físico y archivos
  duplicados descartados por sha256. Segunda pasada de 40 hojas para estabilidad
  fotométrica, mismas hojas en ambas vistas.
- IoU de lesión: **no declarado**. El conjunto dorado quedó muestreado (40 hojas
  físicas, 51 archivos, 22 calibración / 29 test) pero sin máscaras anotadas:
  `golden.py score` informa 51 hojas esperando anotación. Sin esa referencia no
  se puede afirmar que la segmentación mejoró, solo que se movió.
- Estabilidad fotométrica, mismo contenido con brillo 0,75: IoU entre máscaras
  mediana **0,897** (peor 0,289) con la vista canónica contra **0,862** (peor
  0,000) con la visual. La vista visual perdía la máscara completa en al menos
  una hoja; la canónica nunca bajó de 0,289.
- Separación tejido sano / cola de lesión (`p99 − p50` del puntaje): 0,092 →
  **0,112** (+22 %). Mediana del puntaje sobre tejido sano: −0,068 → **−0,144**.
- Área de lesión: mediana **2,21 % → 0,33 %**, p90 9,79 % → 3,21 %, máximo
  53,05 % → 67,66 %; hojas por encima de 20 %: 5 → 3.
- Casos: `IMG_20231015_110914_14` 16 componentes / 3,30 % → 4 / 0,32 % y la
  nervadura central deja de contarse como lesión; `IMG_20231015_111721_8`
  36 / 13,14 % → 2 / 0,37 % (marcaba pliegues en sombra);
  `IMG_20231015_111757_15` (clorótica) 55,35 % → 74,65 %.
- Repetibilidad: dos inspecciones de la misma hoja dan máscara idéntica, área
  idéntica (0,003239), mismo conteo (4) y las 14 capas iguales píxel a píxel.
  Ninguna etapa nueva usa azar.
- Fuga de datos: ninguna. El muestreo descarta 48 archivos duplicados por sha256
  antes de repartir y separa calibración/test por hash del nombre de la hoja, no
  por archivo, para que dos variantes no caigan en lados distintos.
- Fallos: la extensión de la mancha se subestima cuando el halo es pálido (el
  umbral toma el núcleo); la hoja clorótica sigue sin poder separarse por color
  porque todo su tejido sano es amarillo. Ambas son limitaciones declaradas.
- Veredicto: **APTO con reserva** para avanzar a histéresis, **NO APTO** para
  declarar mejora de segmentación. La reserva se levanta cuando `golden.py
  score` tenga n ≥ 30 con máscaras y declare IoU medio y peor caso.

---

## 2026-10-21 — producción en Vercel (demo efímera)

- n: 1 hoja externa (primer plano USDA ARS, 880×1085) subida contra la URL
  pública; el almacén de producción arrancó vacío y volvió a quedar vacío.
- Flujo real: `POST /api/inspections` → `201` con 99 lesiones y 6,22 % de área
  afectada; el PNG de resultado y el original se sirven desde `/media`;
  `GET /api/reports/lot` responde `200` con el registro; `DELETE
  /api/inspections` → `204` y `GET /api/inspections` → `[]`.
- Interfaz: «servicio en línea · v0.1.0», Almanaque «sin inspecciones» tras el
  vaciado, «Limpiar» deshabilitado con archivo vacío y «Actualizar» habilitado.
  Informe vacío correcto («0 imágenes aceptadas», «SIN DATOS», sin imágenes),
  «Guardar» deshabilitado. Cero mensajes de consola y cero respuestas 4xx/5xx
  en 13 pedidos: `/`, `/api/health`, `/api/config`, `/api/inspections`,
  `/api/reports/lot` y las fuentes.
- Layout: sin desborde horizontal a 1440×900 (1425 px de ancho útil) ni a
  390×844 (375 px); la página apila en una columna en móvil.
- Configuración efectiva en producción: storage `/tmp/fellowship-storage`,
  `max_upload_bytes` 4 MB (`GET /api/config`), 60 s de duración máxima.
- Fuga de datos: ninguna; `.vercelignore` excluye `imgs/`, `storage/`,
  `docs/`, `fellowship/`, `tests/` y `sandbox/`, y el almacén local no viaja.
- Observación menor: en la ventana headless, Escape no cerró el diálogo del
  informe; el botón «Cerrar» sí. No se pudo distinguir si es un artefacto del
  evento sintético o un defecto real; queda como chequeo manual pendiente.
- Veredicto: APTO para demo. El almanaque es de sesión por diseño (ADR-012):
  no se acredita persistencia entre instancias.

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
