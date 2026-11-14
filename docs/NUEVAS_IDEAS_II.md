# Conclave "Segunda Misión II" — sesión extraordinaria SIN restricciones

Acta consolidada del conclave de los diez agentes. Mandato de esta sesión:
explorar un **segundo proyecto de procesamiento de imágenes** sin la norma
ADR-002 (habilita cualquier técnica gratis: CV clásico, ML tradicional, DL
ligero en inferencia ONNX/CPU), 100 % gratuitable y ejecutable en el equipo de
Nicolas. Dominios distintos al tabaco. This acta does not amend
`docs/DECISIONES.md`; una dirección elegida se convertirá en el ADR-001 de su
propio repositorio.

## 0. Hallazgos de la sesión (medidos, no recordados)

1. **El hardware real es mejor que la premisa.** Aragorn y Sam lo verificaron en
   el equipo: i5-12500H (16 hilos), 16 GB de RAM, **GTX 1650 de 4 GB presente**
   (torch_cpu no la ve, pero `onnxruntime-directml` puede usarla sin CUDA).
   La restricción dura no es la GPU: son **~3 GB de RAM libres** y **Python
   3.14.3 en el venv** mientras `.python-version` declara 3.12 (bomba de
   trazabilidad: el `method_fingerprint` no incluye intérprete ni versiones).
2. **Costos medidos de las primitivas actuales** (Legolas): máscara clásica
   800×800 ≈ 117 ms; **GrabCut 400×400 ≈ 1.14 s** — el refinamiento clásico del
   core 1 ya cuesta lo que costaría un U²-Net ONNX.
3. **Dos defectos del core 1 que viajan al proyecto 2** (Gimli, medido):
   `cv2.arcLength` sin procesar sobreestima el perímetro +5.3 % y confunde
   circularidad con tamaño (disco r=100 → 0.9015); `RETR_EXTERNAL` oculta
   huecos (mancha vs orificio indistinguibles). `lesion_color_delta` (Merry)
   es euclidiano sobre Lab 8-bit de OpenCV, no CIE ΔE76/ΔE00: pondera L ~2.55×.
   Arreglos de ~2 y ~40 líneas que benefician a ambos proyectos.
4. **Deuda de verdad** (Boromir): el gold set del proyecto 1 tiene
   `human: 0 / auto: 38`. Antes de prometer un segundo gold set, la sesión
   recomienda cerrar al menos una decena de máscaras humanas del 1.
5. **Verificación web parcial**: solo Gandalf tuvo búsqueda real. Las licencias
   citadas por los demás van con etiqueta de confianza y checklist de
   verificación (§6). Ninguna idea se aprueba con firma hasta abrir la página
   de términos de cada dataset.

## 1. Las 12 direcciones puestas sobre la mesa (por proponente)

| # | Dirección | Proponente(es) | Dominio | Técnica central | Esfuerzo |
|---|-----------|----------------|---------|-----------------|----------|
| 1 | **Calibre óptico / Verdad física** (metrología 2D de piezas planas con patrón impreso + calibre digital) | Gimli (A), Boromir (cand. 1) | industria/taller | homografía ArUco/Charuco + silueta + cotas mínimos cuadrados + incertidumbre declarada. 100 % clásica | 2.5–6 sem |
| 2 | **Cartulario / SELLO** (auditoría de lotes de digitalización + extracción con verificación determinista) | Gandalf (2.º), Merry– no, Aragorn (1.º), Pippin (RECIBO) | documentos | compuerta geométrica/frecuencia + hash perceptual + OCR ONNX (RapidOCR, Apache-2.0) + **compuerta de consistencia** (checksum CUIT/IBAN, aritmética ítems↔total) | 3–9 sem |
| 3 | **El Escriba** (papel bajo luz hostil: recorte + rectificación donde el contraste está en la textura, no en el color) | Legolas (1.º) | documentos/foto celular | seg. por contraste de textura local (la sombra cambia L, no la textura del papel) + homografía; DL de respaldo condicionado | 6–8 sem |
| 4 | **Vivero / PLACA** (recuento de colonias en agar fotografiado) | Aragorn (3.º), Legolas (2.º), Gimli (B) | laboratorio/alimentos | histéresis ADR-014 + watershed con marcadores + compuerta confluencia; Cellpose/StarDist ONNX solo en fusiones | 5–7 sem |
| 5 | **Forja / Ojo Fijo** (detección de anomalía solo-con-OK en superficies) | Gandalf (1.º), Pippin (3.º) | industrial QC | PatchCore (anomalib, Apache-2.0) + inferencia ONNX CPU 1–3 s/imagen | 3–10 sem |
| 6 | **Dúplex** (curador de bibliotecas fotográficas: dedupe + triage, nunca borra) | Pippin (1.º) | archivo personal | sha256 → pHash/dHash → embeddings MobileNet opcionales + union-find de ráfagas + QualityGate como scoring keeper | 3–5 sem |
| 7 | **El Cartógrafo** (plano levantado con escala: mm² reales + curvas de nivel sobre la foto) | Celebrimbor (1.º) | oficios/medición | homografía con referencia (A4/moneda) + MobileSAM por clic + Depth Anything Small **solo ordinal** | 4–5 sem |
| 8 | **RustGrade** (severidad de oxidación en acero por color+textura) | Merry (1.º) | infraestructura | índices de óxido en Lab real (h_ab 40–90°, C*≥18), ΔE00, GLCM/LBP; oro ordinal ISO 4628 contra carta pictórica | 4–6 sem |
| 9 | **Censo de copas** (recuento y delineación de árboles desde ortofoto) | Aragorn (2.º) | forestal/urbano | teselado + watershed con prior de tamaño + MobileSAM propuesto + **fusión de costuras** (la etapa difícil) | 7–9 sem |
| 10 | **Parcela** (serie temporal NDVI por polígono de lindes FTW) | Gandalf (3.º) | satelital | sin aprendizaje: recorte de polígonos + z-score contra vecinas + alerta | 5–7 sem |
| 11 | **Guardabosques** (fauna en cámaras trampa) | Legolas (3.º), Frodo (3.º) | ecología | prefiltro clásico por diferencia de ráfaga + MegaDetector + SAM por prompts | 8–10 sem |
| 12 | **La Linterna** (buscador semántico local con mapa de atención) | Celebrimbor (3.º) | archivo | MobileCLIP ONNX + sqlite-vec + heatmaps de atención como explicación | 6–8 sem |

Descartes con razón declarada: restauración de fotos familiares *interactiva*
(Sam la mantiene solo como lote con QC: "no inventamos píxeles" es el producto);
e-commerce recorte de fondo (Legolas: rembg/BiRefNet ya tapan el hueco);
Lesiones cutáneas y retina (Gimli/Boromir: licencia NC + software médico
regulado, indefendible por una persona); EPP/casco en CCTV (Pippin: un falso
negativo silencioso = alguien se lastima); calorías desde foto (Pippin: mortal
por física, profundidad irrecuperable); clasificación de especies de plantas
(heredado del acta anterior, vetada).

## 2. Familias — donde converge el conclave

Las 12 direcciones son en realidad **tres familias**, y esa convergencia entre
agentes que no hablaron entre sí es la señal más fuerte del acta:

### Familia M — Metrología trazable ("la verdad la compra el instrumento, no el anotador")
Cand. 1, 7, 8. Gimli, Boromir y Celebrimbor independientes llegaron al mismo
punto: **el oro más barato del universo de proyectos posibles es una referencia
física** (calibre de 60 USD, cinta métrica, carta ISO 4628, patrón impreso), no
un ejército de anotadores. Hereda directo el prerrequisito 2 del acta anterior
(`ScaleCalibration` inmutable + banda de error de borde + registro por
componente) y lo construye de una vez. Boromir: es la única métrica que
"survive a un auditor hostil sin panel humano". Foso de honestidad compartido:
publicar mm solo con incertidumbre expandida declarada; el Cartógrafo prohibe
exportar profundidad monocular como métrica (ordinal o nada).

### Familia A — Auditoría con compuertas deterministas ("el modelo propone, la medición dispone")
Cand. 2, 3, 4, 5, 6, 9, 11. El patrón Fellowship (compuerta que rechaza con
motivo medido + trazas + informe de lote) aplicado a dominios donde existe una
**verdad auto-declarable**: un checksum de CUIT, una suma ítems↔total, un
conteo humano replicable, un memory-bank de piezas buenas. Aragorn propone el
contrato nuevo para toda la familia: **ADR "El modelo propone, la medición
dispone"** — ningún componente aprendido fija umbrales ni valores publicados;
sus pesos entran al `method_fingerprint` (sha256 + runtime); su salida pasa por
compuerta de consistencia determinista o la corrida se corta. Gandalf, con
búsqueda web real, verificó que el ecosistema de herramientas es libre
(anomalib Apache-2.0 con export ONNX; RapidOCR ONNX; DocLayNet CDLA-Permissive
comercial OK; RVL-CDIP y MVTec NO comerciales).

### Familia E — Color/apariencia como estado
Cand. 8 y el gradiente de Placa. Merry verificó la química (hematita → +a*,
goethita → +b*: la señal y el estado comparten causa física) y trajo la
condición: **ΔE00 en unidades reales primero** (el bug actual lo invalida para
publicar umbrales) y contraste intra-imagen solo (sin carta en cuadro, nada
absoluto es defendible — lección ADR-013 ya pagada).

## 3. Matriz de consolidación

| Cand. | Viabilidad | Esfuerzo | Reuso stack 1 | Oro/validación | Riesgo principal |
|-------|-----------|----------|----------------|----------------|------------------|
| 1 Calibre óptico | **A** | 2.5–6 sem | ~90 % | **Físico, trazable, gratis** (calibre + 20 piezas) | sesgo por espesor/paralaje; solo piezas planas |
| 2 SELLO documental | **A−** | 5–9 sem | **~90 %** (casi textual) | Barato: la regla la da el propio documento (checksum/aritmética) | necesita 1 cliente nombrable; doc nítida vs remuestreada exige panel humano |
| 3 Escriba papel | **B+** | 6–8 sem | 85 % | Propio: 300 fotos + `anotar.py` (1–2 sem de pintado) | sin dataset público del problema; hueco puede no doler |
| 4 Placa/Vivero | **B** | 5–7 sem | **~95 %** | Doble humano + fantasma sintético exacto (Poisson) | mercado chico (CellProfiler ocupa el caso duro); licencias BBBC/ABACo sin verificar |
| 5 Forja anomalía | **B** | 3–4 sem demo | ~70 % | MVTec solo demo (NC); producto exige fotos de cliente | AUROC 0.99 es en laboratorio; taller con luz variable baja sin avisar |
| 6 Dúplex | **B+** | **3–5 sem** | 80 % | Sintético gratis (degradaciones controladas) | regla "nunca borra" es el producto entero; RAW/HEIC fallback ruidoso |
| 7 Cartógrafo | **B** | 4–5 sem | ~75 % | Cinta métrica, día 1 | homografía robusta es metrología no CSS; depende de cand. 1 |
| 8 RustGrade | **B−** | 4–6 sem | 90 % | Cartas ISO 4628 (re-derivar bandas) + cupones propios | licencias NEU-DET/MVTec sin verificar; ilum. dominante es el enemigo |
| 9 Censo copas | **B−** | 7–9 sem | ~65 % | DeepSpot/TreeCount (lic. a verificar) | error de costura; RAM 3 GB exige streaming de teselas |
| 10 Parcela FTW | **C+** | 5–7 sem | ~60 % | Polígonos abiertos (lic. por país!) | el ecosistema FTW puede publicar tu capa analítica arriba tuyo |
| 11 Guardabosques | **C** | 8–10 sem | 65 % | CC BY pero sin máscaras públicas | 55 h/100k imágenes con SAM; MegaDetector ya ocupa el nicho |
| 12 Linterna | **C** | 6–8 sem | ~60 % | 20 consultas propias | recall mediocre = producto vacío; CLIP genérico falla en vocabulario de dominio |

## 4. Ranking final (viabilidad × esfuerzo × reutilización × defensibilidad)

1. **Calibre óptico (cand. 1)** — A. Gana por la razón más aburrida y más
   fuerte: **su verdad de terreno no la anota nadie**. Un calibre digital y una
   tabla Charuco impresa compran la validación. Es además el prerrequisito 2
   del acta anterior ya ejecutado, deja mm/ΔE listos para RustGrade, Cartógrafo
   y Placa, y sus criterios de falsación (|sesgo| ≤ 0.02 mm, SD ≤ 0.01 mm, o se
   publican píxeles) se firman antes de mirar una imagen. Boromir APTO CON
   CONDICIÓN (declarar el sesgo por espesor).
2. **SELLO documental (cand. 2)** — A−. La reutilización más alta (Aragorn:
   "casi textual") y la única con **verificación aritmética interna**: un
   checksum que no cierra no es una opinión, es un rechazo. El gap de mercado
   verificado por Gandalf: todos venden extracción (ABBYY, Document AI), nadie
   vende auditoría del lote con rechazo trazable. Condición de Boromir/Aragorn:
   sin un cliente nombrable es un ejercicio.
3. **Dúplex (cand. 6)** — B+. El MVP más corto (3–5 sem), el gold set sintético
   más barato (degradaciones controladas sobre tus propias fotos), y la regla
   "marca, nunca borra" elimina por diseño la única catástrofe irreversible.
   Pippin la pone primera por modos de fallo; entra tercera por ser más
   herramienta personal que producto defendible ante terceros.
4. **El Escriba (cand. 3)** — B+. El hueco técnico real verificado por quien
   lo midió: U²-Net/rembg no ven papel blanco-sobre-blanco con sombra; el
   discriminator física (textura vs luminancia) es explicable y no es un
   modelo. Pierde ante las anteriores porque el oro hay que pintarlo a mano.
5. **Forja anomalía (cand. 5)** — B. Gandalf la puso primera (Factor D 5/5,
   el músculo nuevo por semana invertida); Boromir y Pippin la bajan: MVTec es
   no-comercial, y el producto real necesita cámara fija + cliente. Demo de 2
   semanas en `sandbox/` barata de ejecutar y con veredicto inmediato.
6. **Placa (cand. 4)** — B− como producto (mercado chico, CellProfiler) pero
   A− como banco de pruebas del fantasma sintético y de la compuerta de
   confluencia. Legolas nota que es literalmente "otro tipo de mancha".
7. **Cartógrafo (cand. 7)** — B− sin cand. 1, A− con cand. 1. Celebrimbor: el
   artefacto (lámina topográfica imprimible) es el diferenciador, no la
   pantalla. Nace fusionada con el ganador #1.
8–12. RustGrade, Censo, Parcela, Guardabosques, Linterna — vitrina posterior;
   cada una hereda la infraestructura de las primeras tres sin justificar
   arrancar por ellas.

## 5. Contratos nuevos que esta sesión exige antes de código

1. **ADR "El modelo propone, la medición dispone"** (proposed by Aragorn,
   endorse unánime implícito): tres cláusulas — umbrales y valores publicados
   solo de etapas deterministas; sha256 de pesos + runtime en
   `method_fingerprint`; compuerta de consistencia determinista sobre toda
   salida aprendida. Sin este ADR no entra ONNX a ningún camino publicado.
2. **ADR de extracción del esqueleto** (`core/common/`, `NotALeaf` →
   `OutOfDomain`): prerrequisito 1 del acta anterior, sigue pendiente y es
   innegociable si habrá dos cores.
3. **ADR de corrida asíncrona** (`POST → 202 + consulta`): con `maxDuration:
   60` y 1 GB de función, ni un lote de escaneo ni 500 teselas caben en el
   `POST` síncrono actual. La cola vive en Neon; el worker, en el equipo local.
4. **Fix del fingerprint de entorno**: `.venv` 3.14.3 vs `.python-version` 3.12
   y paddlepaddle sin wheel (verificado por Aragorn) — el segundo proyecto fija
   3.12 y registra intérprete + versiones en la huella.
5. **Fixes heredables del core 1** (Gimli/Merry): perímetro con `approxPolyDP`,
   `RETR_CCOMP` para huecos, registro por objeto, ΔE00 en unidades reales.
   Benefician a Fellowship exista o no el proyecto 2.

## 6. Checklist de verificación web (deuda declarada de la sesión)

Solo Gandalf tuvo búsqueda real. Antes de firmar cualquier cand.:
- Licencias: DocLayNet/PubLayNet (CDLA-Permissive?), RVL-CDIP (research-only,
  ya confirmado NO comercial), MVTec AD/AD2 + VisA + NEU-DET + Severstal
  (NO comerciales — confirmado parcial), DeepSpot/TreeCount (CC BY?), BBBC por
  dataset, ABACo, BeeCount, Fruits 360 (CC BY?), Snapshot (CC BY vía LILA).
- Herramientas: `onnxruntime` wheel para la versión de Python elegida;
  `onnxruntime-directml` cargando en la GTX 1650 (media jornada de prueba);
  RapidOCR ONNX s/página y RAM pico; MobileSAM/rembg/isnet IoU vs `isolation.py`
  sobre 10 máscaras doradas propias; anomalib en MVTec bottle (AUROC real en
  CPU, no la del paper).
- Productos: existencia/precios de Canopy, TreeQubed, ProtoCOL; si
  FiftyOne/Roboflow ya hacen normalización fotométrica de lote con proveniencia.

## 7. Experimentos de decisión (una tarde cada uno, antes de apostar semanas)

1. **Metrología** (Gimli/Boromir): imprimir tabla A4, medir 10 discos con
   calibre, correr homografía + cotas → sesgo y SD. Criterio: |sesgo| ≤ 0.15 mm
   en cota recta = viva; si no, degrada a pasar/no-pasar.
2. **OCR + compuerta** (Aragorn/Pippin): RapidOCR ONNX sobre 100 páginas mixtas
   — s/página, RAM pico, % de campos extractables + checksum que cierran.
3. **Papel hostil** (Legolas): 30 fotos propias de documento bajo sombra;
   (a) textura-vs-luminancia clásico, (b) rembg isnet, (c) MobileSAM bbox.
   IoU declarado antes de ver. Si (b) gana por >0.05, "El Escriba" pierde su
   razón clásica y pasa a rectificación+auditoría.
4. **Anomalía** (Gandalf): anomalib PatchCore en MVTec bottle/capsule en CPU —
   AUROC e inferencia reales. 2 h, veredicto duro.
5. **Ráfagas** (Pippin): pHash + union-find sobre tu propio imgs/ — ¿el
   clustering recupera las 210 hojas de verdad? El set actual ya es un corpus.

## 8. Votaciones y disidencias

- **Gandalf** votó Forja primera (músculo nuevo por semana); el acta la deja
  quinta porque Boromir y Pippin le demostraron el techo de licencia y de
  cliente. Gandalf lo acepta: "medir en semana 1 o bajar la promesa".
- **Aragorn** votó SELLO primera; acepta el voto de Boromir/Gimli de que la
  familia M (metrología) construye antes el prerrequisito del que SELLO vive.
- **Pippin** votó Dúplex primera (modos de fallo más baratos); el ranking la
  deja tercera por defensibilidad ante terceros, no por técnica.
- **Boromir** dejó su objeción en el acta: `human: 0` en el gold set del
  proyecto 1 es una deuda de verdad; propone cerrar ≥10 máscaras humanas antes
  de juramentar el proyecto 2.
- **Celebrimbor**: la identidad visual del proyecto 2 no toca el pergamino ni
  la puerta redonda — latón y papel milimetrado para la familia M.
- **Unanimidad**: ningún modelo aprendido fija umbrales ni publica valores;
  todo DL es propuesto bajo compuerta determinista, o no entra.

---
*Acta firmada por: gandalf, aragorn, sam, legolas, gimli, merry, pippin,
boromir, celebrimbor, frodo. Sesión extraordinaria sin restricción ADR-002,
2026-10-31. Nota de herramienta: solo gandalf dispuso de web search; el resto
declaró su confianza por afirmación.*
