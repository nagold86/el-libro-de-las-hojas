# Decisiones (ADRs)

Registro ligero: una sección por decisión, la más reciente arriba. Toda decisión
que cambie el contrato, el método o las rutas necesita una entrada acá, escrita
por Gandalf y aprobada por quien resulte afectado.

---

## ADR-015 — La clorosis se mide por ángulo de matiz, no por canales de color

**Contexto.** ADR-014 resolvió el halo pardo, pero la clorosis seguía sin nombre.
El criterio de lesión es "rojo alcanza al verde", y un tejido amarillo pálido no
es rojo: el detector lo contaba como parte de la mancha sin poder decir qué era.
La hoja `IMG_20231015_111757_15`, la clorótica de control, salía con 72,83 % de
área afectada y sin forma de saber cuánto de eso era pardo y cuánto amarillo.

Se probó primero la diferencia de canales, `(b* − a*) / 255`, y **falló al revés**:
las hojas sanas de este dataset ya son amarillo-verdosas (`a* ≈ −28`, `b* ≈ 48` →
0,30) y la clorótica tiene menos croma (`a* ≈ −1`, `b* ≈ 35` → 0,13). Lo que
cambia no es cuánto amarillo hay, sino **cuánto verde se perdió**, y eso es un
ángulo, no una diferencia.

**Decisión.** La clorosis es una familia aparte con su propio detector
(`core/chlorosis.py`), que no toca la máscara de lesión:

- Puntaje `b* / (|a*| + b*)` en Lab sobre la vista canónica (ADR-013). Vale 0,63
  en tejido verde, 0,97 en tejido amarillo y 0,69 en tejido pardo.
- Umbral **0,85**, fijo, sin calibración por hoja: el criterio ya es un ángulo y
  el dataset no lo pide. Se deja declarado en `PipelineSettings`
  (`chlorosis_hue_threshold`) por si la calibración lo mueve.
- Croma mínimo 10 para descartar grises, brillos y ruido, donde el ángulo no
  significa nada.
- Apertura y cierre 5×5 y área mínima 60 px: la clorosis es una mancha grande y
  difusa, nunca un píxel suelto.
- Se mide con el mismo morfómetro que la lesión y viaja como `chlorosis` en el
  contrato, con su propio bloque en la traza. **No se suma al área afectada.**

**Consecuencia aceptada.** En 63 hojas, el solape mediano entre las dos máscaras
es del 100 %: el tejido amarillo casi siempre cae dentro de la máscara parda,
porque el amarillo también tiene algo más de rojo que de verde. La clorosis no es
"área nueva", es **una parte etiquetada de lo afectado**. Por eso la pantalla la
muestra pegada al área afectada y no como una cifra que se suma.

**Evidencia.** Calibración sobre 31 hojas (ver `sandbox/calibrar_clorosis.py`):
mediana 0,646; por encima de 0,85 queda 0,3 % de la superficie en la hoja mediana
y 3,0 % en el p90; el máximo (21,3 %) es una hoja con necrosis severa, no una
hoja sana. La control clorótica da 0,906 de mediana y 64,6 % de superficie por
encima del umbral. De punta a punta (`sandbox/auditar.py`): clorosis mediana
0,0275 % de la superficie, p90 3,94 %, y en la control 57,98 % con solape 100 %.

**Alternativas descartadas.** (a) Sumar la clorosis al área de lesión: duplicaría
la superficie afectada en la control. (b) Restarla del área de lesión: dejaría
una hoja clorótica reportada como sana, que es peor error que el actual.
(c) Umbral por hoja sobre el percentil del propio puntaje: convertiría el detector
en un detector de "lo más amarillo de cada hoja" y marcaría manchas en hojas
perfectamente sanas.

**Reversibilidad.** `chlorosis_hue_threshold` por encima de 1 desactiva la
familia sin tocar código. La capa, el bloque de contrato y la métrica desaparecen
juntos si se quita el detector de `build_pipeline`.

**Afecta a.** `core/chlorosis.py` (nuevo), `core/pipeline.py`, `core/orchestrator.py`,
`core/render.py`, `app/schemas.py`, `app/routers/inspections.py`, `frontend/app.js`,
`frontend/index.html`, `frontend/tokens.css`, y los tests de orquestador y contrato.

---

## ADR-014 — La máscara se arma con dos umbrales: uno siembra y el otro crece

**Contexto.** ADR-013 dejó la segmentación midiendo la vista canónica y el área de
lesión cayó de 2,21 % a 0,33 % de mediana. Esa caída no era error sino extensión:
con el umbral 0 lejos del tejido sano, la máscara tomaba el núcleo oscuro de la
mancha y dejaba afuera el halo pardo que la rodea. Un único umbral obliga a elegir
entre marcar el halo pálido o marcar el tejido sano, porque en el histograma las
dos poblaciones se tocan en las hojas con poco margen.

**Decisión.** `LesionSegmenter` trabaja en dos tiempos.

- **Semillas**: el umbral estricto de siempre (`redness_threshold = 0`) más
  apertura, cierre y el filtro de área y compacidad. Son los componentes que
  existen, y siguen siendo la única fuente de manchas.
- **Crecimiento**: desde cada semilla, dilatación geodésica sobre los píxeles que
  superan un umbral bajo, con techo de `hysteresis_max_growth_px = 8` píxeles y
  excluyendo la máscara de nervaduras del detector de venas.

El umbral bajo no es una constante: sale de la distribución de la propia hoja,
`p50` del puntaje sobre superficie válida, y se ubica una fracción
(`hysteresis_fraction = 0,5`) del camino hacia el umbral estricto. Un piso
(`hysteresis_max_drop = 0,15`) impide que una hoja con margen enorme arrastre
verde al halo. Si la hoja no tiene margen (p50 ≥ umbral), los dos umbrales
coinciden y no se crece nada. La traza gana la capa `segmentacion_histeresis`,
que pinta el núcleo en terracota plena y el halo en terracota lavada.

**Consecuencia aceptada.** La máscara vuelve a incluir el halo y la extensión
sube, pero sigue lejos del sobre-marcado de la vista con balance: **0,60 % de
mediana contra el techo de 2,21 %**. El crecimiento nunca puede inventar una
mancha: todo componente crecido está conectado a una semilla, así que el conteo
de componentes no cambia (348 → 348 sobre 63 hojas).

**Evidencia.** 63 hojas analizables del dataset (17 quedaron fuera de política por
nitidez), mismo pipeline con histéresis apagada y encendida. Área mediana
**0,36 % → 0,60 %** (factor **1,35×**, p90 2,16×); p50 sano mediano **−0,143**,
umbral bajo mediano **−0,071** (exactamente la mitad del camino); el piso de
−0,15 no se alcanzó en ninguna hoja. Componentes: 348 antes y 348 después, máximo
por hoja 37 y 37, **0 hojas con más componentes**. Hojas sin lesión: 9 antes y 9
después. `IMG_20231015_110914_14`: 4 componentes y 0,32 % → 4 y 0,75 % — el halo
del ampollado vuelve y la nervadura central sigue fuera. `IMG_20231015_111721_8`:
2 y 0,39 % → 2 y 0,59 % — los pliegues en sombra siguen fuera. La hoja clorótica
`IMG_20231015_111757_15` tiene p50 +0,053, así que el umbral bajo coincide con el
estricto y no crece (77,97 % → 78,13 %): el caso degenerado se comporta como se
declaró.

**Medición contra el conjunto dorado (provisional).** 38 máscaras prellenadas por
el detector previo: IoU medio 0,750 (peor 0,189), Dice 0,845, precisión 0,618,
recall 1,000. **No es exactitud**: la referencia es la salida del propio detector
con histéresis apagada, así que recall 1,000 es una identidad (el crecimiento
expande) y el IoU mide cuánto se movió, no cuánto acierta. Coincide con la
inflación medida en el auditor (1/0,75 ≈ 1,33×). El número que falta es el que
sale de corregir esas 38 máscaras a mano.

**Alternativas descartadas.** Bajar el umbral estricto a un valor fijo negativo:
reproduce exactamente el problema de ADR-013, porque el valor óptimo depende de
cada hoja. Umbral bajo por percentil del tejido sano (p95 del sano) sin tope de
profundidad: sobre una nervadura fina el crecimiento se propaga sin límite,
porque el canal es continuo. Rellenar huecos por morfología: agranda el radio de
forma pareja y no distingue halo de vena. Filtrar los componentes después del
crecimiento: sobra, porque el crecimiento no crea componentes y el filtro ya se
aplicó a las semillas.

**Reversibilidad.** Alta: `PipelineSettings(hysteresis=False)` reproduce la
máscara de un solo umbral de ADR-013, y los tres parámetros de crecimiento son
configuración declarada.

**Afecta a.** Legolas (segmentación), Gimli (la extensión medida sube), Boromir
(veredicto y conjunto dorado), Aragorn (parámetros declarados), Celebrimbor (capa
nueva en la traza).

---

## ADR-013 — La imagen que se mide no lleva balance de blancos ni CLAHE

**Contexto.** El usuario reportó que la detección de manchas «no está clara». Una
auditoría sobre las 210 hojas del dataset (una por hoja, variantes colapsadas)
mostró que el problema no era el criterio sino el camino hasta él: el balance de
blancos gray-world de `core/preprocess.py` corregía la imagen que después se
segmentaba, y en una hoja verde **las 210 hojas tenían al menos una ganancia
pegada a sus límites** (G en 0,75 y B en 1,33 en la mayoría). Corregir el color
por el promedio de la escena sube el rojo de todo el tejido: la mediana del
puntaje `(R − G)/(R + G)` sobre tejido sano pasaba de −0,068 a −0,144 según la
vista, dejando el umbral 0 a menos de 0,03 de distancia en las peores hojas. El
CLAHE sobre L hacía lo mismo con el histograma local. El criterio declarado en
ADR-007 es invariante al brillo global; el preproceso le quitaba esa propiedad.

**Decisión.** `StandardPreprocessor` devuelve dos vistas de la misma hoja:

- `image` — **vista de análisis**: el recorte tal cual, solo con el bilateral
  suave. Es lo único que entra a la segmentación, la morfometría y los
  descriptores. Lleva `params["analysis_view"] = "canonica_sin_balance"`.
- `display` — **vista de presentación**: balance de blancos + CLAHE en luminancia
  + bilateral, en ese orden. Es la que se muestra y la que juzga la puerta de
  calidad. Lleva `params["white_balance_applies_to"] = "display"`.

La traza gana una capa, `preproceso_analisis`, que abre la etapa, y las capas de
balance y contraste pasan a titularse «(visual)» con la explicación de por qué no
miden. La puerta de calidad sigue leyendo `display` porque `min_sharpness = 15`
se calibró sobre esa imagen y 27/210 hojas dependen de esa calibración; medirla
sobre la vista canónica exigiría recalibrar el umbral, que es otra decisión.

**Consecuencia aceptada.** El área de lesión baja: mediana **2,21 % → 0,33 %**,
p90 **9,79 % → 3,21 %**. No es una pérdida de precisión sino de **extensión**: la
máscara toma el núcleo oscuro de la mancha y deja fuera el halo parduzco, porque
el umbral 0 ahora está lejos del tejido sano en vez de rozarlo. `IMG_20231015_110914_14`
pasa de 16 componentes y 3,30 % a 4 componentes y 0,32 %, y la nervadura central
que se contaba como lesión desaparece. La recuperación de la extensión le
corresponde a la histéresis (próxima etapa) y se juzga con IoU, no con área.

**Evidencia.** 210 hojas: mediana del puntaje sano −0,068 → **−0,144**, mínimo
−0,104 → −0,213. 40 hojas: separación `p99 − p50` **0,092 → 0,112** (+22 %).
Estabilidad bajo brillo global 0,75: IoU mediana **0,862 → 0,897**, mínimo
**0,000 → 0,289** (la vista visual perdía la máscara completa en al menos una
hoja). `IMG_20231015_111721_8`: 36 componentes / 13,14 % → 2 / 0,37 % (marcaba
pliegues en sombra). La hoja clorótica `IMG_20231015_111757_15` pasa de 55,35 % a
74,65 %: ambas vistas marcan el tejido no verde, la canónica lo delimita mejor,
y el criterio sigue sin distinguir clorosis de necrosis.

**Alternativas descartadas.** Quitar el balance de blancos de raíz: la pantalla
necesita una imagen legible y el balance sigue sirviendo para eso. Recalibrar
`min_sharpness` sobre la vista canónica en la misma decisión: cambia el veredicto
de calidad de 27/210 hojas y no hay referencia anotada para justificarlo.
Normalizar el puntaje por hoja (mediana/MAD) en lugar de sacar el balance: es la
etapa siguiente y también necesita el conjunto dorado. Dejar `display` como
vista única y documentar el sesgo: ya estaba documentado en ADR-007 y no se
cumplía.

**Reversibilidad.** Alta: es una expresión en `StandardPreprocessor.apply` y un
campo del resultado; `image` y `display` conviven, así que volver a medir sobre
`display` es cambiar un argumento en tres llamadas del orquestador.

**Afecta a.** Sam (preproceso), Legolas (segmentación), Merry (descriptores,
que ahora describen la hoja y no la corrección), Boromir (calidad y veredicto),
Aragorn (orquestación), Celebrimbor (capa nueva en la traza).

---

## ADR-012 — Demo en Vercel con almacenamiento efímero declarado

**Contexto.** El MVP corría solo en local, con FastAPI y OpenCV sobre el disco
del proyecto. El usuario pidió publicarlo: un repositorio nuevo en GitHub con lo
necesario y un despliegue en Vercel. El backend es Python con OpenCV, SciPy y
NumPy, y el almanaque escribe en disco; Vercel ejecuta funciones serverless con
el proyecto de solo lectura, `/tmp` escribible y efímero, y un cuerpo de pedido
limitado a 4,5 MB.

**Decisión.** Se publica la app completa (pantalla y API) como una única función
Python en Vercel, con `vercel.json` apuntando a `app/main.py` (60 s de duración
máxima). `Settings.from_env()` (`app/config.py`) detecta `VERCEL` y, sin tocar el
código, cambia dos valores: el repositorio pasa a `/tmp/fellowship-storage` y el
límite de subida baja a 4 MB para dejar margen al `multipart`. En local no cambia
nada: sigue `storage/` y 10 MB. `FELLOWSHIP_STORAGE_DIR` sigue siendo la vía para
apuntar a un volumen o servicio externo sin recompilar.

**Consecuencia aceptada.** El almanaque de la demo es de sesión: sobrevive
mientras la instancia siga caliente y puede vaciarse al reiniciarse o al caer en
otra instancia. El botón «Limpiar» y el informe funcionan sobre lo que haya en
esa instancia. Es una demo de contrato y de método, no un servicio de producción
con historial garantizado; la página lo advierte en el README.

**Alternativas descartadas.** Storage externo (S3/R2/Supabase) desde el primer
deploy: exige cuenta, credenciales y un repositorio asíncrono, y no era necesario
para cerrar el MVP; queda como evolución natural porque el repositorio es
inyectable. Solo frontend en Vercel con la API en Render/Fly: dos servicios y dos
cuentas para una demo. Servir el informe como PDF generado en el servidor:
sumaría dependencias y el HTML autocontenido ya se imprime igual.

**Evidencia.** Producción responde `200` en `/api/health`, `/`, `/api/config`,
`/api/inspections` y `/api/reports/lot`. El flujo real se verificó contra la URL
pública: subida `201` con 99 lesiones y 6,22 %, PNG y original servidos, y
`DELETE /api/inspections` dejando el almanaque vacío. En navegador: «en línea»,
cero errores de consola, cero respuestas 4xx/5xx, sin desborde horizontal a
1440 px ni a 390 px.

**Reversibilidad.** Alta: los dos valores viven en `config.py` y `vercel.json`.
Conectar un storage persistente es cambiar una variable de entorno.

**Afecta a.** Aragorn (despliegue y contrato), Frodo (persistencia y artefactos),
Boromir (qué se puede afirmar de una demo efímera).

---

## ADR-011 — Vaciar el almanaque con una sola ruta idempotente

**Contexto.** El Almanaque solo permitía borrar una inspección por vez. Limpiar
las pruebas exigía N clics o N pedidos desde la consola; un fallo a mitad de
camino dejaba un estado parcial y el cliente no tenía una operación declarativa
para vaciar el archivo. El usuario pidió un botón «Limpiar» para eliminar las
fotos del almanaque antes de cerrar el MVP.

**Decisión.** `DELETE /api/inspections` (`app/routers/inspections.py`) delega en
`InspectionRepository.clear()` (`app/repository.py`) y responde `204` sin cuerpo.
La operación es idempotente: con el almanaque vacío también responde `204`. El
repositorio recorre solo `*.json` cuyo nombre cumple `ID_PATTERN` y, por cada id,
borra el original, el resultado, el JSON y sus `.tmp` atómicos; `.gitkeep` y
cualquier archivo ajeno quedan intactos. La pantalla reutiliza el `<dialog>` de
confirmación con un estado `pendingClear`: muestra «¿Vaciar el almanaque?», la
cantidad real de inspecciones y el botón «Vaciar archivo». El botón queda
deshabilitado con el almanaque vacío o mientras hay una operación en curso.

**Evidencia.** `tests/test_repository.py` verifica que `clear()` borra dos
registros con sus artefactos y conserva `.gitkeep`; `tests/test_contract.py`
verifica `204`, listado vacío y `404` para cada id borrado. La suite completa
pasa con 125 tests. En Edge headless, con cuatro inspecciones: cancelar la
confirmación no envía ningún `DELETE` y conserva las cuatro; confirmar envía
`DELETE /api/inspections` (204), el Almanaque queda «sin inspecciones», el panel
de resultado se oculta, el botón Limpiar se deshabilita y no hay errores de
consola.

**Limitación declarada.** No hay papelera ni deshacer: el borrado es definitivo.
La ruta no tiene autenticación ni alcance por usuario; la app es local y de un
solo operador. No toca artefactos fuera de `storage/` ni archivos cuyo nombre no
sea un id válido.

**Alternativas descartadas.** Iterar `DELETE /api/inspections/{id}` desde el
frontend (N pedidos, fallos parciales y estado ambiguo); borrado lógico con
tombstones (agrega estado y contradice «vaciar»); vaciar el directorio desde el
sistema operativo (puede llevarse `.gitkeep` o archivos ajenos y evita el
contrato).

**Reversibilidad.** Alta: la ruta es aditiva; quitar el botón y la ruta no
requiere migración de datos.

**Afecta a.** Frodo (persistencia y artefactos), Aragorn (contrato), Celebrimbor
(confirmación y estados), Boromir (auditoría destructiva).

---

## ADR-010 — Informe del lote calculado al leer, no persistido

**Contexto.** El Almanaque ya listaba inspecciones sueltas, pero no respondía la
pregunta del lote: cuántas hojas se escanearon, cuánto daño hay en conjunto, cómo
se distribuye y cuáles son las peores. Sumar en el cliente sobre
`GET /api/inspections` habría duplicado la regla de agregación y abierto la
puerta a cifras distintas entre pestañas. El usuario pidió un botón «Informe»
con números y gráficos para entender el lote escaneado.

**Decisión.** `GET /api/reports/lot` (`app/routers/reports.py`) delega en
`build_lot_report` (`app/reporting.py`) y responde `LotReportOut`
(`app/schemas.py`). El informe se agrega **al leer** sobre `repository.list()`,
es decir, sobre las inspecciones aceptadas: un rechazo no entra al lote. No hay
tabla de informes ni caché; cada pedido refleja el storage vigente. El contrato
expone totales (imágenes, lesiones, media y mediana de área, Feret máximo,
nervaduras, pardeamiento y nitidez), cuatro cortes operativos de severidad
(Sano < 1 %, Leve 1–5 %, Moderado 5–15 %, Severo ≥ 15 %), el nivel dominante
(empate → el más severo), hasta cinco peores hojas, la lista completa de puntos,
el conteo de advertencias de calidad y el conteo de métodos de aislamiento. Los
registros viejos sin `trace.isolation` se leen con método `desconocido`; los
campos faltantes caen a 0 para no romper el informe. La pantalla usa un
`<dialog>` nativo con sello, cifras, histograma, dispersión, ranking y tabla
imprimible; los SVG los dibuja `app.js` sin biblioteca de gráficos.

**Extensión 2026-10-21 — Copia guardable.** El botón **Guardar**, junto a
Imprimir, serializa la hoja renderizada a una página HTML autocontenida
(`tokens.css` y `styles.css` embebidos, SVG y tablas en línea) y la escribe con
`showSaveFilePicker` en la carpeta que elija el usuario; si la API no está
disponible, cae a una descarga normal. No cambia el contrato ni agrega
dependencias: el archivo se abre sin el servidor y conserva la impresión A4. Los
botones del informe se sustituyen por texto en la copia para no dejar controles
muertos.

**Evidencia.** Con cuatro fotos USDA y un registro legado: 5 imágenes, 342
lesiones, mediana de área 8,73 %, peor 38,43 %, dominante severo, conteos
0/1/2/2 (0/20/40/40 %), métodos `desconocido` 1, `grabcut` 3 y `primer_plano` 1.
La pantalla se verificó en Edge headless con CDP: 4 barras de histograma, 5
puntos de dispersión, 5 barras de ranking y 5 filas de tabla, sin errores de
consola ni pedidos fallidos; a 390×844 la tabla se lee como fichas. La impresión
produjo un PDF A4 de 4 páginas legible. `tests/test_report.py` cubre lote vacío,
cortes, empate, peor hoja, registro legado y forma del contrato.

**Limitación declarada.** El informe describe solo lo aceptado: las 27 hojas
rechazadas por nitidez (ADR-009) no aparecen y el lote parece mejor de lo que
fue. Los cortes 1/5/15 % son operativos, no agronómicos; sin patrón de escala no
hay milímetros. No hay ponderación por área foliar, intervalos de confianza ni
agrupación temporal. El ranking grafica como máximo cinco hojas; el resto vive
en la tabla. Los gráficos dependen de JS: sin `GET /api/reports/lot` no hay
figura, aunque las tablas de datos son el respaldo en pantalla.

**Alternativas descartadas.** Agregar en el cliente sobre
`GET /api/inspections` (duplicaría la regla y podría divergir); persistir un
informe por corrida (quedaría obsoleto al borrar una inspección); Chart.js
(dependencia nueva para tres gráficos simples); generar el PDF en el servidor
(más superficie y otra fuente de verdad).

**Reversibilidad.** Alta: la ruta es aditiva y no toca las inspecciones; el
informe se puede retirar sin migrar datos.

**Afecta a.** Aragorn (contrato y agregación), Celebrimbor (diseño e impresión),
Boromir (auditoría del lote), Gimli (medidas), Frodo (storage y legado).

---

## ADR-009 — Aislamiento de hoja antes de analizar (enmienda a ADR-003)

**Contexto.** ADR-003 declaró que las 2000 imágenes del dataset son recortes de
superficie foliar y que no había segmentación hoja/fondo. Eso sigue siendo
cierto para el dataset, pero la API acepta fotos nuevas con fondo, mano o mesa.
Sin aislamiento, el balance de blancos y las máscaras se contaminan: una pared
verde o una mano pueden entrar como superficie válida y las lesiones se miden
sobre píxeles que no son hoja. El usuario pidió dejar solo la hoja y retirar el
fondo.

**Decisión.** El pipeline antepone `LeafIsolator` (`core/isolation.py`, Legolas)
y queda: aislamiento → preproceso → calidad → dominio → segmentación →
morfometría → descriptores. Sobre la imagen original se construye un prior verde
con ExG y HSV (saturación y matiz), se limpia con morfología, se elige la
componente más grande y se refina con GrabCut inicializado por máscara
(`GC_INIT_WITH_MASK`) y `cv2.setRNGSeed(0)`. Si el prior cubre ≥ 97 % del
encuadre, se conserva la imagen completa (`primer_plano`): un recorte ahí solo
destruiría nervaduras. Si la componente verde es < 0,5 % se devuelve `sin_hoja`
y el orquestador lanza `NotALeaf` antes de medir. En el resto se recorta al
bounding box, se pinta el fondo de negro y se analiza ese recorte. La imagen
original se sigue guardando y enlazando; el overlay se dibuja sobre el recorte
para que las máscaras coincidan. `InspectionResult` lleva `isolation` y el JSON
`trace.isolation` declara método, tamaños, bbox, fracciones, componentes y
advertencias.

**Evidencia.** Dataset: 210/210 pasan la compuerta de dominio; 183/210 terminan
aceptadas y las 183 usan `primer_plano` (el recorte no cambia ni un píxel).
Externas USDA: `k5992-1` pasa de 2752×1800 a 1136×1380 con hoja 60,0 % y mide 94
lesiones / 4,97 %; `k5992_hoja` conserva 880×1085 con 99 / 6,22 %;
`k5992_parche` queda como primer plano 508×508 con 72 / 8,73 %; `k5993-1` pasa
de 2738×1800 a 2039×1800 con advertencia `varias_regiones_verdes` y mide 63 /
38,43 %. `tests/test_isolation.py` cubre primer plano, escena con fondo, sin
hoja, determinismo y recorte.

**Limitación declarada.** El prior es de color: una hoja muy amarilla o pálida
puede requerir el respaldo de GrabCut, y una escena con otra planta verde puede
pasar. Si hay dos hojas verdes, se queda la mayor y solo se advierte
`varias_regiones_verdes`; no se rechaza, y la segunda puede quedar dentro del
recorte. La nitidez se mide sobre el interior erosionado de la máscara válida
para no castigar el borde artificial del recorte; con eso 27/210 hojas del
dataset se rechazan por borrosas (19 con la métrica anterior). Es una reserva de
calidad declarada, no un efecto del aislamiento.

**Alternativas descartadas.** Umbral de verde sin GrabCut (bordes y nervaduras
claras se perdían); segmentación aprendida (prohibida por ADR-002); recorte
manual (no escala a un lote); no aislar (el fondo contaminaba medidas y
dominio).

**Reversibilidad.** Alta: `LeafIsolator` es inyectable
(`LeafInspector(isolator=...)`) y `closeup_fraction`, `min_leaf_fraction`,
`max_side` y `rng_seed` son parámetros. `trace.isolation.method` identifica el
camino en cada registro.

**Afecta a.** Legolas (dueño), Aragorn (orden y contrato), Sam (recibe el
recorte), Boromir (calidad y auditoría), Celebrimbor (overlay sobre el recorte),
Frodo (original y artefactos).

---

## ADR-008 — Compuerta de dominio: una envolvente foliar, no un clasificador

**Contexto.** El pipeline asumía que toda imagen era un recorte de superficie de
hoja. Una foto de documento, una pared o el cielo producían números: el
segmentador de lesiones marcaba "manchas" donde no hay hoja y la API devolvía
`201` con métricas sin sentido. La consigna prohíbe modelos preentrenados, así
que no había un clasificador disponible.

**Decisión.** Antes de segmentar corre `LeafDomainGate` (`core/domain.py`), una
compuerta one-class con seis rasgos interpretables medidos sobre los píxeles
válidos de la **imagen original**: ExG medio, fracción verde (ExG > 0,05),
fracción de matiz verde (H 30–95, S ≥ 40), fracción brillante (> 220), varianza
local 5×5 y entropía de Shannon de 256 bins. Del preproceso solo se reutiliza la
máscara de píxeles confiables: el balance de blancos reparte el verde entre los
tres canales y puede dejar una hoja legítima fuera de todo umbral. Cada rasgo
tiene umbral de envolvente y se rechaza con **dos o más** violaciones. El rechazo
es `NotALeaf` → `422 IMAGE_NOT_A_LEAF` y el motivo nombra cada rasgo medido
contra su umbral. La corrida aceptada registra
`trace.domain = {gate: "envelope_v1", score, features}`.

**Evidencia.** Calibración sobre las 210 hojas originales (una por hoja, sin
variantes), midiendo la imagen original: 210/210 aceptadas; 206 con `score = 0`
y 4 con `score = 1` (tres por matiz verde 46,7 %, 23,1 % y 48,9 %; una por
entropía 5,45 bits), todas dentro de la tolerancia de una violación. Controles
sintéticos: documento 6 violaciones, pared 5, cielo 4, ruido 4; los cuatro
rechazados. La primera calibración (ExG 0,10 / verde 0,55 / matiz 0,40)
rechazaba 2 hojas reales (0,95 %): una con necrosis severa
(`IMG_20231015_111151_13`) y otra con clorosis (`IMG_20231015_111757_15`).
Ambas son hojas: el color no puede ser la barrera principal, porque una hoja
enferma sigue siendo hoja.

**Enmienda 2026-10-21.** Una prueba con fotos externas de USDA ARS (dominio
público, `sandbox/externas/manifest_usda.json`) encontró un falso rechazo: el
primer plano de una hoja con lesiones de TMV tenía 97,9 % de superficie verde y
96,1 % de matiz verde en crudo, pero el balance de blancos gray-world lo dejaba
en 22,7 % y 9,8 %, y la compuerta lo rechazaba. La compuerta pasó a medir la
imagen original; los umbrales de color se recalibraron a ExG 0,10 / verde 55 % /
matiz 50 % y los demás no cambiaron. Con eso el primer plano pasa con
`score = 0`, un recorte con hoja y mano pasa con `score = 0`, y las dos escenas
completas (hoja sostenida, invernadero) siguen rechazadas con verde 20,7 % y
41,2 % y matiz 20,1 % y 40,9 %.

**Limitación declarada.** La compuerta no autentica especie ni calidad: una
textura verde de otra planta pasa. Los umbrales de color son deliberadamente
laxos para la enfermedad (ExG 0,10; verde 55 %; matiz 50 %), pero exigen que la
hoja domine el encuadre: una escena con la hoja pequeña se rechaza. La barrera
real sigue siendo textura y entropía. `trace.domain` hace la decisión auditable,
pero no sustituye la inspección visual de casos raros.

**Alternativas descartadas.** Clasificador aprendido (prohibido por la
consigna); un solo umbral de verde (rechazaba hojas enfermas); Otsu sobre
saturación (inestable entre tomas); exigir una firma de nervaduras (la clorosis
borra el contraste).

**Reversibilidad.** Alta: `DomainThresholds` es un dataclass congelado e
inyectable, y `LeafInspector(domain_gate=...)` permite sustituirlo.
`trace.domain.gate` identifica la versión en cada registro.

**Afecta a.** Boromir (dueño de la compuerta), Aragorn (orden del pipeline y
contrato), Legolas (recibe solo imágenes dentro de dominio), Celebrimbor
(mensaje de error legible en pantalla).

---

## ADR-007 — La lesión se define por pardeamiento (rojo ≥ verde), no por Otsu

**Contexto.** La primera versión de `LesionSegmenter` puntuaba cada píxel con una
mediana en Lab y umbralizaba con Otsu. Sobre `imgs/IMG_20231015_110914_14.png`
marcaba el 49,8 % de la superficie, incluida la mitad sana: el umbral global se
desplazaba por las sombras y separaba "mitad clara / mitad oscura" en vez de
"tejido sano / tejido pardo".

**Decisión.** El puntaje es `(R − G) / (R + G + 1e-3)`, umbral `> 0`, con
apertura y cierre 5×5 y descarte de componentes por área mínima
(`max(24 px, 0,0002 · píxeles válidos)`) y compacidad (`≥ 0,15`). El criterio es
invariante a la iluminación global: una sombra multiplica R y G por el mismo
factor y no cambia el signo.

**Evidencia.** Cuantiles de `(R − G)/(R + G)` en la imagen citada: mediana
−0,043 y percentil 99 = 0,032. Con umbral 0 el área medida baja de 0,498 a 0,033
(16 componentes) y el overlay coincide con las manchas visibles. La misma imagen
repetida como `augmented_116_2.png` produce un resultado idéntico, lo que además
confirma la duplicación del dataset.

**Limitación declarada.** La clorosis (amarillo, R ≈ G) y las manchas casi
blancas no se detectan con este criterio; requieren un segmentador propio. El
trazado lo hace explícito: `trace.segmentation.step = "redness_threshold"`.

**Alternativas descartadas.** Otsu sobre Lab (ver contexto); umbral absoluto de
croma (13–27 % de área, seguía marcando tejido sano); `(R − G)` sin normalizar
(depende de la exposición).

**Reversibilidad.** Alta: umbral y filtros son parámetros de `LesionSegmenter`, y
`PipelineSettings` fija el área mínima de la corrida.

**Afecta a.** Legolas, Gimli, Boromir, Aragorn.

---

## ADR-006 — Décimo agente de diseño visual (aliado, no miembro)

**Contexto.** El producto necesita una capa visual propia, no un frontend de
tablero genérico. La Comunidad tiene nueve miembros y el diseño no estaba
representado: nadie respondía por identidad, legibilidad ni por el overlay de
máscaras.

**Decisión.** Se agrega `celebrimbor` como décimo agente, con rango de **aliado**
fuera de los Nueve. Gobierna `docs/DESIGN.md`, `frontend/tokens.css`,
`frontend/styles.css`, `frontend/index.html` y `core/render.py`. No mide, no
segmenta, no orquesta y no modifica contratos: si la pantalla necesita otro dato,
lo pide por ADR.

**Alternativas descartadas.** Dar el diseño a Aragorn (mezclaría integración con
identidad y volvería a él juez de su propia interfaz); usar un tema genérico
(no distingue el producto y no resuelve la legibilidad del overlay).

**Métrica de aceptación.** Contraste AA (4.5:1) en texto normal, foco visible con
teclado y los tres estados de pantalla (vacío, error, resultado) capturados en
`docs/DESIGN.md`. El overlay distingue lesión y nervadura sin tapar la textura.

**Reversibilidad.** Alta: el diseño vive en `frontend/` y un único módulo de
render; el contrato HTTP no depende de él.

**Afecta a.** Celebrimbor, Aragorn, Legolas, Gimli, Boromir.

---

## ADR-005 — Desvíos deliberados del template del TP2

**Contexto.** El template define `core/`, `app/`, `tests/`, `storage/`,
`frontend/`. Este proyecto necesita tres carpetas más y un cambio de nombre en el
directorio de datos.

**Decisión.** Se agregan `imgs/` (dataset dado, inmutable), `data/` (derivados de
ingesta: manifest y duplicados) y `sandbox/` (experimentos de Pippin); se conserva
`fellowship/` como documentación del equipo de agentes. `storage/` queda
exclusivamente para artefactos de la API.

**Alternativas descartadas.** Meter el dataset en `storage/` (se mezclarían datos
dados con artefactos generados y el repository tendría que ignorarlos);
manifest dentro de `docs/` (es un derivado regenerable, no documentación).

**Métrica de aceptación.** `test_architecture.py` falla si el core importa `app`,
FastAPI o `starlette`; ningún test escribe en `imgs/`.

**Reversibilidad.** Alta: mover `data/` y `sandbox/` no afecta el contrato HTTP.

**Afecta a.** Frodo, Pippin, Aragorn, Boromir.

---

## ADR-004 — La unidad de muestreo es la hoja, no la imagen

**Contexto.** `imgs/` tiene 2000 archivos pero solo 210 originales: 1680 son
variantes de 8 por hoja y 110 son variantes con nombre duplicado. Además hay 42
grupos de duplicados exactos por sha256.

**Decisión.** Toda métrica agregada, toda muestra de validación y todo veredicto
se agrupan por hoja base. Las variantes nunca cuentan como muestras
independientes: se usan para robustez y repetibilidad, o no se usan.

**Alternativas descartadas.** Tratar cada PNG como una observación (infla n por
8 y produce métricas falsamente estables); usar solo las aumentadas (son
transformaciones, no capturas nuevas).

**Métrica de aceptación.** Ningún informe declara `n = 2000`; el n se declara en
hojas. Boromir rechaza cualquier lote que mezcle variantes de la misma hoja entre
calibración y evaluación.

**Reversibilidad.** Baja una vez publicados resultados; alta antes de la primera
corrida.

**Afecta a.** Frodo, Boromir, Pippin, Aragorn.

---

## ADR-003 — El objeto de análisis es la superficie foliar, no la hoja completa

**Contexto.** Las 2000 imágenes son recortes de superficie de hoja de tabaco
(800×800, sin fondo visible, sin contorno completo). No existe una vista de hoja
entera sobre mesa o fondo uniforme.

**Decisión.** El pipeline analiza **defectos y apariencia**: manchas necróticas,
clorosis, orificios, nervaduras, uniformidad y textura. No se implementa
segmentación hoja/fondo ni morfometría de hoja completa. Las medidas de defectos
se expresan en píxeles y en fracción del área de la imagen hasta que exista
calibración física.

**Alternativas descartadas.** Forzar un contorno de hoja inexistente (produce
máscaras inventadas); inferir tamaño real sin patrón de escala (números sin
significado).

**Métrica de aceptación.** La segmentación se evalúa con IoU contra anotación de
lesiones en `tests/golden/`, no contra contornos de hoja.

**Reversibilidad.** Media: si aparece un lote con hoja completa, se agrega un
`Segmenter` nuevo sin tocar el orquestador.

**Afecta a.** Legolas, Gimli, Merry, Sam, Boromir.

**Enmienda 2026-10-21.** ADR-009 antepone un aislamiento hoja/fondo para fotos
nuevas con fondo. El dataset sigue sin necesitarlo (las 183 hojas aceptadas se
analizan como `primer_plano`), pero la afirmación «no hay segmentación
hoja/fondo» ya no describe el pipeline completo.

---

## ADR-002 — Solo visión clásica

**Contexto.** El objetivo del proyecto es caracterizar hojas con procesamiento
de imágenes, no entrenar modelos. Hay 210 hojas, insuficientes para aprendizaje
supervisado honesto, y sin etiquetas de grado.

**Decisión.** Se usan únicamente operaciones deterministas: espacios de color,
umbrales, morfología, filtros, descriptores geométricos, matrices de co-ocurrencia
y patrones binarios locales. Cualquier incorporación de aprendizaje automático
requiere un ADR nuevo.

**Alternativas descartadas.** Segmentación con modelos preentrenados (caja negra,
sin trazabilidad, dependencia pesada); aumento de datos para entrenar (las
variantes ya existen y son el problema, no la solución).

**Métrica de aceptación.** `pyproject.toml` no declara torch, tensorflow,
ultralytics ni transformers; un test de arquitectura verifica que el core no los
importe.

**Reversibilidad.** Baja: cambiaría la naturaleza del proyecto.

**Afecta a.** Todos.

---

## ADR-001 — El core es una librería sin dependencias de HTTP

**Contexto.** El TP2 demostró que separar `core/` de `app/` permite usar el mismo
motor desde la API, la CLI y los tests, y que la frontera se puede verificar.

**Decisión.** `core/` no importa FastAPI, `starlette` ni nada de `app/`. La API
solo valida, delega y persiste. El orquestador es `core/orchestrator.py` y recibe
sus estrategias por inyección.

**Alternativas descartadas.** Un módulo único con FastAPI adentro (imposible de
testear sin levantar el servidor); lógica en los routers (fue el origen de las
regresiones del TP2).

**Métrica de aceptación.** `tests/test_architecture.py` importa `core` en un
subproceso y afirma que no se cargó ningún módulo de FastAPI, starlette ni `app`.

**Reversibilidad.** Alta al inicio, nula después de la primera entrega.

**Afecta a.** Aragorn, todos los dueños de módulos del core.
