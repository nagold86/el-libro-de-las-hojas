# Decisiones (ADRs)

Registro ligero: una sección por decisión, la más reciente arriba. Toda decisión
que cambie el contrato, el método o las rutas necesita una entrada acá, escrita
por Gandalf y aprobada por quien resulte afectado.

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
