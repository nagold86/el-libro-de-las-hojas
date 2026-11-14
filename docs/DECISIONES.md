# Decisiones (ADRs)

Registro ligero: una sección por decisión, la más reciente arriba. Toda decisión
que cambie el contrato, el método o las rutas necesita una entrada acá, escrita
por Gandalf y aprobada por quien resulte afectado.

---

## ADR-026 — La edición manual corrige máscaras, medidas e informes

**Contexto.** ADR-025 guardaba los trazos como referencia aparte, sin alterar
las cifras. Eso impedía que la persona corrigiera una lesión o una zona
clorótica que el método no había reconocido, y el informe seguía mostrando la
medición anterior.

**Decisión.** Al guardar, volver a ejecutar el método desde la imagen original y
reaplicar la secuencia completa de trazos: `healthy` elimina lesión y clorosis,
`diseased` fuerza la máscara de lesión, `chlorosis` fuerza la máscara de clorosis
y `erase` devuelve esos píxeles a la clasificación automática. Recalcular
morfometría y descriptores con las máscaras corregidas, persistir las medidas y
regenerar el overlay/capas. El informe del lote consume esas medidas e incluye
clorosis y un indicador de hojas editadas; severidad sigue basada en lesión y no
mezcla clorosis con pardeamiento.

**Alternativas.** Mantener los trazos como referencia sin efecto queda
descartado porque no cumple la corrección solicitada. Sumar lesión y clorosis
en una sola máscara queda descartado porque duplicaría o confundiría familias.

**Métricas de aceptación.** Una corrección de enfermedad debe mover las
métricas por clase y la fila correspondiente del informe; corregir a sano debe
reducirlas; borrar un trazo debe restaurar exactamente la máscara automática en
esa zona. Al reabrir, overlay y medidas deben coincidir con los trazos guardados.

**Reversibilidad.** Completa: se conserva la secuencia normalizada de trazos y
cada guardado vuelve a procesar el original; borrar los trazos restaura el
resultado automático.

**Afecta a.** `core/manual_annotations.py`, `core/orchestrator.py`, ambos
repositories, `app/routers/inspections.py`, `app/media.py`, `app/reporting.py` y
el editor/informe del frontend. Este ADR supersede la semántica de referencia
sin efecto de ADR-025.

---

## ADR-025 — Las correcciones manuales son referencias, no métricas automáticas

**Contexto.** Una persona necesita poder señalar tejido sano y enfermo para
revisar visualmente el detector, pero sustituir en silencio la máscara automática
volvería opacas las cifras del pipeline y las agregaría al informe del lote como
si las hubiera producido el método.

**Decisión.** Guardar trazos manuales vectoriales, normalizados al recorte
analizado, en un campo `manual_annotations` separado. El usuario puede marcar
`healthy` o `diseased` y borrar trazos; los registros llevan fecha de edición.
Las medidas y capas automáticas permanecen intactas.

**Alternativas.** Sobrescribir máscaras y recalcular métricas queda descartado
porque mezcla criterio humano y automático. Guardar solo la imagen del canvas
queda descartado porque impide revisar y editar trazos individuales.

**Métricas de aceptación.** Guardar y volver a abrir debe conservar exactamente
los trazos y el encuadre; coordenadas fuera de `[0, 1]` deben rechazarse; las
métricas automáticas deben permanecer iguales antes y después.

**Reversibilidad.** Completa: borrar `manual_annotations` deja intactos el
resultado y las capas generadas por el método.

**Afecta a.** `app/schemas.py`, `app/store.py`, ambos repositories,
`app/routers/inspections.py` y el editor manual del frontend.

---

## ADR-024 — Segunda segmentación clásica por luminancia normalizada y cromaticidad

**Contexto.** El método vigente mezcla umbrales de rojo y oscurecimiento local.
Una sombra de borde puede tener una respuesta local fuerte aunque mantenga el
color del tejido; clorosis y pardeamiento también necesitan criterios distintos.
El proyecto limita el análisis a visión clásica, sin entrenamiento ni modelos.

**Decisión.** Agregar `core2` como alternativa determinista e intercambiable:
estimar iluminación amplia con un suavizado gaussiano en Lab L*, normalizar luminancia, proponer lesiones
por cromaticidad parda o por oscuridad residual con cambio cromático, y separar
clorosis con cromaticidad amarilla frente a verde. Conservar `core` como valor
predeterminado y registrar la alternativa usada en cada inspección.

**Alternativas.** Ajustar otro umbral de oscuridad fue descartado porque no
representa explícitamente iluminación; un segmentador aprendido fue descartado
por la restricción del proyecto y la falta de máscaras multiclase suficientes.

**Métricas de aceptación.** En pruebas sintéticas, una sombra uniforme no debe
producir píxeles de lesión ni clorosis, mientras que manchas pardas, necrosis
acromática y tejido amarillo deben conservarse. La aprobación agronómica queda
pendiente hasta medir IoU por hoja contra anotaciones humanas; esta decisión no
declara `core2` superior sobre imágenes reales.

**Reversibilidad.** Completa: `core` sigue disponible y es el método por defecto;
la selección de `core2` queda aislada por inspección.

**Afecta a.** `core2/`, `core/pipeline.py`, `app/routers/inspections.py`,
`app/media.py` y el selector del frontend.

---

## ADR-023 — La compuerta juzga el tejido del recorte, no el verde de la escena

**Contexto.** El aislamiento aprendió a recortar por contraste con el fondo y dejó
de suponer que la hoja es verde (ADR-020). La compuerta, en cambio, seguía
pidiendo exceso de verde, superficie verde y matiz verde. Son tres rasgos que en
una hoja sana se cumplen juntos y en una hoja seca se incumplen juntos: con
`allowed_violations = 1` bastaba que el tejido no fuera verde para rechazar la
foto con `422 IMAGE_NOT_A_LEAF` («verde insuficiente»). Sobre las fotos de hoja
entera del banco externo el resultado era el peor posible: las dos hojas más
curadas se rechazaban y las dos más verdes pasaban.

Segundo problema, más silencioso: la varianza local se medía en una ventana de
5×5 píxeles sobre la imagen tal como venía. La misma hoja fotografiada a 165 px
medía 714 y a 1800 px medía 283: el límite superior de 400 no describía el
tejido, describía la resolución del archivo. Con ese límite, cualquier foto chica
quedaba a un rasgo del rechazo.

**Decisión.**

- **El color es una familia, no un color.** Se reemplazan `min_exg`,
  `min_green_fraction` y `min_green_hue_fraction` por un único
  `min_tissue_fraction`: fracción del recorte con matiz en `[5, 95]` de OpenCV
  (del ocre al verde azulado) y saturación ≥ 40. Una hoja sana, una clorótica y
  una curada caen dentro; el cielo, el papel y la pared sin croma quedan afuera.
  El ExG medio se sigue publicando como lectura de apoyo, pero ya no decide.
- **La textura se mide a tamaño de referencia.** Antes de calcular varianza y
  entropía, el recorte se lleva a 600 px del lado menor (`INTER_AREA` si achica,
  `INTER_LINEAR` si agranda) junto con su máscara válida. Agrandar suaviza el
  grano de una foto chica y achicar promedia el de una grande, así que un tejido
  parecido mide parecido: sobre el banco externo, 129–312 en lugar de 714–1815
  para las mismas hojas.
- **El peso del rechazo pasa a la textura.** Una pared o un cielo limpio son lisos
  (textura plana) y una imagen de un solo nivel no tiene nervaduras que medir
  (entropía fuera de rango). Ese es el control que sostiene la compuerta ahora
  que el color dejó de exigir verde.
- **Los siete valores de la envolvente son ajustables.** Entran al catálogo de
  ADR-022 en el grupo «compuerta», anidados en
  `PipelineSettings.domain_thresholds` para no cambiar la forma del ajuste:
  `Tuning.to_settings()` los separa y los aplica con `replace`. Una combinación
  imposible —textura mínima mayor que la máxima— sale como `InvalidTuning`
  (`422 INVALID_THRESHOLDS`) y no como error interno.

**Consecuencias.**

- Las hojas curadas dejan de rechazarse: sobre el banco externo pasan las cinco,
  con `tissue_fraction` entre 0,54 y 1,00 y textura entre 129 y 312.
- `envelope_v1` conserva su nombre porque el contrato lo publica, pero sus rasgos
  cambian; por eso cambió la huella del método y cada registro viejo queda
  identificado con la suya (ADR-016).
- El ruido blanco ya no lo corta la compuerta sino el aislamiento, que no
  encuentra forma que recortar (`sin_hoja`). Es el reparto correcto: la compuerta
  opina sobre un recorte de hoja, no sobre el sensor.
- Se acepta una pérdida de protección: una superficie parda con forma de hoja
  —una mesa de madera clara— podría pasar la compuerta. Se prefiere eso a exigir
  verde, que rechazaba el producto.

**Alternativas descartadas.** Exponer los umbrales viejos sin tocar el criterio:
habría destrabado la foto de hoy y dejado el criterio equivocado adentro, con el
operario bajando el mínimo de verde lote por lote. Hacer que la compuerta juzgue
la forma del objeto aislado: pide mover la etapa y rompe el orden de la traza que
fija el contrato.

---

## ADR-022 — Los umbrales se ajustan por corrida, no se editan en el código

**Contexto.** Los umbrales del método vivían dentro de `PipelineSettings` y solo
se cambiaban tocando el código, con dos consecuencias: cada lote atípico pedía un
deploy, y la huella del método (ADR-016) cambiaba sin que nadie supiera por qué.
Abrirlos a ciegas rompe el contrato en dos formas: una corrida sin traza de lo que
se movió no se puede repetir, y un valor absurdo puede dejar el pipeline midiendo
basura o levantando un `ValueError` que la API devuelve como `500`.

**Decisión.**

- **Un catálogo, una verdad.** `core/tuning.py` declara los parámetros
  ajustables con rango, paso, unidad, grupo y explicación en castellano
  (`PARAMETERS`). `GET /api/thresholds` publica el catálogo junto con los defectos
  resueltos desde `PipelineSettings`: la pantalla no repite rangos, los consume.
  (Dieciséis desde ADR-023.)
- **El ajuste no toca la estructura.** `Tuning.to_settings()` devuelve un
  `PipelineSettings` completo con lo movido aplicado. Lo que no está en el
  catálogo —la histéresis, el orden de las etapas— no se puede mover desde afuera:
  se ajusta cuánto, no cómo. (La compuerta de dominio se sumó al catálogo en
  ADR-023.)
- **Se valida al entrar.** `Tuning.from_json` (HTTP) y `from_public` (registro
  guardado) lanzan `InvalidTuning`, que el manejador traduce a
  `422 INVALID_THRESHOLDS` con el nombre del parámetro y su rango. Un `null`
  significa «defecto»; una clave desconocida se rechaza cuando llega del cliente
  y se ignora cuando se relee un registro viejo.
- **Cada corrida se firma con su huella.** Con ajustes, la API arma un
  `LeafInspector` aparte con `build_pipeline(settings)` y calcula
  `method_fingerprint(settings)`: el registro guarda la huella de esa corrida. El
  inspector de la aplicación no se toca, así que dos pedidos no se contaminan.
- **El registro guarda lo movido, no el catálogo.** `trace.tuning` lleva solo los
  valores distintos del defecto (vacío = corrida por defecto). Con eso `/media`
  rearma el mismo pipeline (`inspector_for`) y el overlay regenerado sigue siendo
  byte a byte el que se vio; si el ajuste guardado ya no se puede reconstruir, se
  avisa por log y se cae al defecto antes que romper la descarga.
- **Viaja como campo de formulario.** `POST /api/inspections` acepta un campo
  `tuning` de texto con el JSON al lado del archivo (`multipart`). Un campo
  hermano del archivo no obliga a cambiar el tipo de contenido ni a subir dos
  veces.

**Consecuencias aceptadas.** Dos corridas de la misma foto con umbrales distintos
son dos registros y dos huellas: el informe del lote (ADR-016) las separa en vez
de promediarlas. Un ajuste guardado que ya no cierra degrada la descarga del
overlay a los defectos y el PNG puede no coincidir con el que se midió, y por eso
se avisa. Un pedido ajustado construye un inspector que se descarta al terminar:
el costo es de milisegundos y la alternativa era un inspector mutable compartido.

**Alternativas descartadas.** (a) Un `POST /api/thresholds` que persista el
ajuste global: convertiría un cambio de exploración en un cambio de método para
todos, y el archivo histórico quedaría midiendo con otra regla sin decirlo. (b)
Umbrales por variables de entorno: siguen necesitando un redeploy. (c) Aceptar
cualquier número y recortarlo al rango en silencio: el operador creería que midió
con lo que pidió. (d) Guardar el catálogo entero en cada registro: el `trace`
crecería con nueve valores repetidos y la comparación entre corridas se volvería
ruidosa.

**Reversibilidad.** Alta. Sin el campo `tuning` la ruta se comporta como antes, y
un registro sin `trace.tuning` se rehace con el inspector de la aplicación.

---

## ADR-021 — Dos evidencias para una mancha, y las nervaduras antes que ellas

**Contexto.** ADR-007 marcaba mancha con un solo criterio de color: el índice de
pardeamiento `(R−G)/(R+G)` por encima de un umbral. Funcionaba con la muestra y
falla con lo que llega de campo: una mancha oscura sin corrimiento de tono apenas
mueve el índice, y la red de nervaduras —más oscura que la lámina— entraba en la
máscara como si fuera lesión.

**Decisión.**

- **Las nervaduras se detectan primero.** `VeinEnhancer` combina *black-hat* y
  *top-hat* a dos escalas, umbraliza contra el percentil pedido y filtra por
  elongación: una vena es fina y alargada, una mancha es compacta. El resultado
es una máscara de venas y, derivada, una `vein_guard` dilatada que el crecimiento
  de la mancha no puede cruzar.
- **Dos evidencias, no una.** Una mancha se propone si el pardeamiento supera
  `redness_threshold` **o** si el píxel es oscuro a escala local —la relación
  mínima entre dos suavizados gaussianos frente al fondo cercano— y a la vez
  pardo o acromático, que es el guardián que evita contar sombras neutras.
  `darkness_threshold = 0` apaga esa segunda evidencia y reproduce el método
  anterior.
- **Crecimiento con tope.** Los píxeles propuestos son semillas; una histéresis
  las expande a los vecinos que ya estaban cerca del umbral, con profundidad
  limitada (`hysteresis_max_growth_px`) y prohibida sobre `vein_guard`. Así una
  mancha de borde difuso se cierra sin invadir la vena.
- **Sin tejido sano no se inventa un umbral.** Si el anillo sano queda vacío
  —una hoja enferma entera— la histéresis se apaga y se mide con el umbral
  nominal, en vez de calcular una mediana sobre una muestra vacía.

**Consecuencias aceptadas.** El segmentador necesita las venas antes y después,
así que corre dos veces: cuesta menos que una máscara que se come la nervadura.
`darkness_threshold` es el parámetro más delicado del catálogo: subirlo recorta
manchas de bajo contraste, bajarlo mete sombras. Un píxel oscuro y pardo a la vez
cuenta una sola vez, así que el conteo no se duplica por tener dos evidencias.

**Alternativas descartadas.** (a) Umbral adaptativo global (Otsu sobre el índice):
con dos poblaciones muy desiguales —poca mancha, mucha hoja— el corte se va al
lado de la mayor y borra la lesión. (b) Segmentar por color en HSV: el pardeamiento
no está en el tono sino en la relación R/G, y el tono del tejido seco se confunde
con el de la mancha. (c) Filtrar las venas después de tener las manchas: la vena
ya estaba dentro de la máscara y la resta deja anillos huecos. (d) Aprender el
umbral por hoja: es un modelo, y ADR-002 lo tiene fuera del alcance.

**Reversibilidad.** Alta, en las dos direcciones: `darkness_threshold = 0` apaga
la segunda evidencia y el defecto de `redness_threshold` deja las manchas pardas
como antes. La barrera de venas se controla con `vein_percentile` y `vein_kernel`.

---

## ADR-020 — El fondo se descarta por contraste, no por ser verde

**Contexto.** El aislamiento de ADR-008 daba por sentado que la hoja estaba sobre
una mesa oscura y que era lo único verde de la imagen: segmentaba por exceso de
verde y recortaba al rectángulo de la hoja. Con imágenes de campo eso se cae en
los tres casos frecuentes: hoja marchita sobre fondo claro, hoja sobre una
superficie también verde, y foto con el fondo casi del color de la hoja.

**Decisión.**

- **El borde manda.** Se muestrea un anillo de píxeles pegado al marco, se toma la
  mediana en Lab como color de fondo y la desviación absoluta mediana como
  dispersión. Cada píxel se mide como distancia normalizada a ese fondo: lo que se
  parece al marco es fondo, sin importar de qué color sea.
- **El verde es un rescate, no el criterio.** El prior de exceso de verde (y su
  versión en HSV) solo se usa cuando el contraste por borde no alcanza a proponer
  nada. Que la hoja tenga manchas pardas o esté amarilla deja de ser un problema.
- **Tres descartes sobre los componentes.** Se tiran por área mínima, por tocar
  el borde del marco y por **cuerpo**: un componente tiene que admitir un disco
  inscrito de radio razonable (`MIN_BODY_FRACTION` sobre el lado menor). El filtro
  de cuerpo es el que separa una hoja de un texto o una barra fina: una raya de
  8 px de alto pasaba el filtro de relación de aspecto y ahora no pasa.
- **Refinado y recorte.** GrabCut pule el contorno con el rectángulo del
  componente ganador como semilla, se rellenan los huecos y se recorta con 2 % de
  margen. El recorte es lo que hace que las máscaras y la imagen del resultado
  midan lo mismo.
- **La compuerta no cambia.** Si nada sobrevive, el resultado es «sin hoja» y la
  API responde 422: el mismo contrato de ADR-008, con otro criterio detrás.

**Consecuencias aceptadas.** Una imagen ya recortada al ras de la hoja —sin marco
de fondo— produce un anillo de borde que es hoja, y el aislamiento puede descartar
todo: el 422 es correcto, pero conviene que el mensaje pida margen. Sobre fondo muy
texturado (madera, tela) la dispersión del anillo sube, el umbral de distancia se
relaja y el recorte puede incluir algo de fondo; el margen del 2 % absorbe lo que
no llega al contorno.

**Alternativas descartadas.** (a) Seguir con el prior de verde y sumarle umbrales
por imagen: cada caso nuevo pedía otra regla. (b) Detectar el objeto más grande
por contorno: un fondo texturado también tiene contornos grandes. (c) Pedirle al
usuario que recorte a mano: no escala y mueve el problema al operador. (d) Un
modelo de segmentación: ADR-002.

**Reversibilidad.** Media. El criterio de borde se controla con
`isolation_sensitivity` desde la pantalla; volver al prior de verde exigiría
reordenar el aislamiento, no solo un valor.

---

## ADR-019 — El overlay final va anotado: contornos, número por mancha y leyenda

**Contexto.** El overlay de ADR-010 mezclaba tres máscaras con transparencia. Se
veía dónde había color, pero no dónde terminaba una mancha ni cuál era cuál: dos
manchas vecinas se leían como una sola, el número del panel no tenía a qué
apuntar, y con la clorosis y las venas encima el ojo no distinguía la capa.

**Decisión.**

- **Un modo, no un reemplazo.** `render_overlay(..., annotate=False)` sigue
  devolviendo exactamente el PNG de antes; `annotate=True` agrega la anotación
  encima. Los tests de tono y forma (ADR-010) no cambian, y las capas de la traza
  siguen siendo imágenes limpias.
- **Contorno por mancha.** Cada mancha detectada se dibuja con su contorno a
  trazo firme y se numera en orden de área decreciente, con el número puesto en
  el punto de mayor distancia al borde de su propia mancha: la etiqueta no cae
  sobre el borde ni fuera de la lesión.
- **Leyenda dentro de la imagen.** Un plato opaco en una esquina lista las capas
  presentes —`lesion`, `nervadura`, `clorosis`— con su muestra de color. Lo que no
  está en la corrida no aparece en la leyenda.
- **El tamaño no cambia.** La anotación se dibuja dentro del mismo lienzo: el
  contrato «el PNG del resultado mide lo mismo que la imagen analizada» sigue
  valiendo.
- **Hasta 24 manchas numeradas.** Más que eso no se lee a tamaño de pulgar y
  numerar el ruido no informa: se dibujan los contornos igual, la numeración se
  corta.

**Consecuencias aceptadas.** La anotación tapa píxeles de la lesión: la imagen
sirve para mostrar, no para volver a medir —para eso están las capas sueltas y la
traza—. La leyenda ocupa una esquina, así que una mancha justo ahí queda
parcialmente tapada. El número sigue el orden de área, no el orden en que se
detectaron: si se mueve un umbral, la numeración se reacomoda.

**Alternativas descartadas.** (a) Anotar siempre: rompe los tests de tono y
ensucia la traza, donde cada capa es una imagen limpia. (b) Etiquetas fuera del
lienzo, en un margen nuevo: cambia el tamaño del PNG y rompe la coincidencia con
las máscaras. (c) Solo la leyenda, sin contornos: no responde «dónde». (d)
Guardar el overlay anotado como una capa más: duplica bytes que ya se pueden
regenerar.

**Reversibilidad.** Alta. Es un argumento con defecto `False`: el modo limpio
existe y no cuesta nada.

---

## ADR-018 — Cada operador ve sus hojas; el administrador ve el almanaque

**Contexto.** ADR-017 dejó un archivo compartido: cualquier operador con sesión
veía, abría, descargaba y borraba las hojas de todos, y el informe del lote
promediaba hojas ajenas. Además, la única puerta de alta era la API
(`POST /api/auth/users`) y no existía ninguna baja: un operador que se iba
conservaba su cuenta, su clave y sus permisos para siempre.

**Decisión.**

- **Alcance de lectura.** El `admin` ve todo el almanaque; el `operador` ve solo
  lo suyo. El filtro `owner` se ignora cuando quien pide es un operador
  (`app/security.py: owner_scope`).
- **Lo ajeno no existe.** Detalle, borrado y PNG de una hoja de otro responden el
  mismo `404 INSPECTION_NOT_FOUND` que un identificador desconocido
  (`can_see`). Un `403` descriptivo confirmaría que la hoja existe.
- **Informe y vaciado también se recortan.** `GET /api/reports/lot` agrega solo
  las hojas del operador y `DELETE /api/inspections` borra solo las suyas. Para
  el administrador las dos rutas siguen hablando del archivo completo.
- **Sin dueño.** `GET /api/inspections?unassigned=true` lista y
  `DELETE /api/inspections?unassigned=true` borra las hojas que no tienen cuenta
  detrás (solo administrador). «Sin cuenta» es `user_id IS NULL` en la base
  —nunca hubo dueño o su usuario se dio de baja por `ON DELETE SET NULL`— y la
  hoja sin `owner` en el payload cuando la persistencia es de archivos.
- **Baja de usuario.** `DELETE /api/auth/users/{id}` borra la fila (`204`). Nadie
  puede darse de baja a sí mismo (`403 SIN_PERMISO`): siempre queda un
  administrador vivo. `404 USUARIO_NO_ENCONTRADO` si el identificador no existe.
  La sesión del dado de baja muere en el acto, porque `authenticate` busca la
  fila en cada pedido.
- **Sus hojas no se borran.** Quedan en el almanaque sin dueño: el
  administrador las sigue viendo y las purga con la ruta de huérfanas cuando ya
  no hacen falta.
- **Contrato del almacén.** `list(..., unassigned=False)` y
  `clear(owner=..., unassigned=...)` en las dos implementaciones (ADR-016), más
  el filtro `unassigned` en la lista del historial.
- **Frontend.** La conserjería (diálogo «Usuarios»: lista con rol, alta con clave
  y rol, baja por fila), el botón «Borrar hojas sin dueño» y la opción «sin
  dueño» del filtro «Quién». El filtro por dueño y la conserjería solo se
  muestran al administrador.

**Consecuencias aceptadas.** «Sin dueño» no significa lo mismo en las dos
persistencias: en archivos no hay cuentas, así que solo es huérfana la hoja que
nunca tuvo dueño (en la base también lo son las de un usuario dado de baja). Un
operador paga una consulta más por descarga de `/media`: el dueño se verifica
antes de generar la imagen. La baja no es suave ni se audita más allá del log.
El administrador pierde el aislamiento: ve todo, que es su trabajo.

**Alternativas descartadas.** (a) Responder `403` en lo ajeno: confirma que la
hoja existe. (b) Borrar en cascada las hojas del usuario dado de baja: la baja de
una cuenta no debería reescribir el archivo histórico ni tirar mediciones que el
lote todavía necesita. (c) Baja suave con `is_active = false`: deja cuentas
zombis y el pedido era eliminar. (d) Un campo `visible` por hoja: multiplica
estados sin resolver nada que el dueño no resuelva. (e) Filtrar solo en el
frontend: el contrato es público y la API se puede llamar sin la pantalla.

**Reversibilidad.** Un administrador puede deshacer el efecto de un borrado de
usuario solo recreando la cuenta (las hojas siguen ahí, sin dueño). El alcance
por dueño se concentra en `owner_scope` y `can_see`: volver al archivo
compartido es cambiar dos funciones y quitar el filtro de las tres rutas.

---

## ADR-017 — Login en la base, sesión firmada y versiones declaradas

**Contexto.** ADR-016 dejó el registro en Postgres, pero la aplicación seguía
abierta: cualquiera con la URL podía subir hojas, vaciar el almanaque y descargar
el informe del lote. Con un archivo compartido hace falta saber **quién** midió
cada hoja. Además, el historial no distinguía con qué versión del software se había
medido: promediar 0,36 % de la 0.1.1 con 0,60 % de la 0.2.0 no significa nada, por
la misma razón por la que no se mezclan huellas de método (ADR-016). Y el almanaque
solo mostraba las últimas inspecciones, sin ningún recorte hacia atrás.

**Decisión.**

- Los usuarios viven en Postgres (`users`: `id`, `username`, `display_name`,
  `password_hash`, `role`, `is_active`). **Sin `DATABASE_URL` no hay login**: la
  demo en archivos se queda abierta y `settings.auth_required` es exactamente
  `settings.uses_database`.
- Contraseñas con `hashlib.scrypt` (N = 2^14, r = 8, p = 1, sal de 16 B, clave de
  32 B) en formato `scrypt$n$r$p$sal$hash`: el costo viaja con el hash, así subirlo
  mañana no invalida las claves viejas. Comparación con `hmac.compare_digest` y el
  mismo trabajo para un usuario inexistente que para uno real, para no delatar
  cuáles existen.
- La sesión es una cookie `HttpOnly`, `SameSite=Lax` y `Secure` **según el esquema
  del pedido**: `payload.firma` en base64url con HMAC-SHA256 sobre
  `{"sub", "exp"}`. No hay tabla de sesiones: cada request valida firma y
  expiración y lee el usuario, así que el esquema no crece con el tráfico y cerrar
  sesión es borrar la cookie.
- Dos roles: `admin` (todo, incluido el alta de usuarios) y `operador` (mide, mira
  y borra). El primer administrador se crea solo en el arranque y solo si la tabla
  está vacía (`FELLOWSHIP_ADMIN_USER` / `FELLOWSHIP_ADMIN_PASSWORD`).
- Guardas en `app/main.py`: con base, todo salvo `/api/health`, `/api/config` y
  `/api/auth/*` exige sesión, **incluidas `/media`**. Sin base no se monta ninguna.
- Cada inspección guarda `owner` dentro del payload (`id`, `username`,
  `display_name`) y `user_id` como columna derivada. La columna se resuelve con
  `(SELECT id FROM users WHERE id = %s)`: si el dueño ya no existe, queda `NULL` en
  vez de romper el guardado, y el nombre sigue en el payload.
- El historial (`GET /api/inspections`) acepta `version`, `owner`, `since`, `until`
  y `q` (nombre de archivo) además de `limit`/`offset`; las dos implementaciones
  del contrato aplican los mismos filtros.
- `software_versions` es el registro de versiones publicadas: el propio guardado
  hace el *upsert* de `app_version` + `method_version`, y `GET /api/versions`
  devuelve versión, huella, notas, cantidad de hojas y ventana temporal. En modo
  archivos la lista se agrega al vuelo (`app/versions.py`), con la misma forma.
- El frontend abre con la puerta: ficha de sesión con nombre y rol, «Salir»,
  filtros de versión / quién / búsqueda, «Cargar más hojas» de a 50 y el sello de la
  versión en cada fila del almanaque.

**Consecuencias aceptadas.** Con base hay que definir el administrador inicial una
vez. El login no tiene recuperación por correo ni bloqueo por intentos: es una
herramienta de campo con usuarios que administra una persona. «Limpiar» se
deshabilita cuando hay un filtro puesto, porque vacía el almanaque entero y no lo
que se ve en pantalla.

**Alternativas descartadas.** (a) OAuth o un proveedor externo: una decena de
operadores conocidos no justifica otra dependencia ni un alta afuera. (b) JWT con
`PyJWT`: la firma HMAC de la biblioteca estándar hace lo mismo sin agregar nada. (c)
Tabla de sesiones: escribir en cada request para poder revocar individualmente algo
que nadie revoca. (d) Usuarios sobre el almacén de archivos: sin base no hay login
que valga y la demo tiene que seguir abriéndose sin credenciales. (e) Login
obligatorio siempre: rompería la demo y los tests que no usan Postgres.

**Reversibilidad.** Con `DATABASE_URL` vacío la aplicación vuelve a abrirse y las
rutas de `/api/auth` responden `400 SIN_AUTENTICACION`. `users` y
`software_versions` se pueden vaciar sin tocar `inspections`, y el payload conserva
`owner` aunque el usuario se borre.

---

## ADR-016 — El registro de análisis vive en Postgres; las capas se regeneran

**Contexto.** ADR-012 dejó la demo en Vercel escribiendo en `/tmp`, que es
efímero: cada arranque en frío se lleva el almanaque entero. Un registro son
18 PNG (original, overlay y 17 capas) más un JSON con el payload, así que
respaldarlos en el propio disco del deploy no es una opción y guardar los PNG
en una base tampoco: medido sobre una hoja del dataset, el overlay y las 17
capas suman 4,3 MB sobre 580 KB de original, y no hay forma de consultarlos.

**Decisión.** Hay una base de datos como registro real y una sola interfaz para
no obligar a nadie a saber cuál está activa.

- `app/store.py` define el `Protocol` `InspectionStore` (`save`, `get`, `list`,
  `delete`, `clear`, `original_bytes`) y `create_app` elige implementación una
  sola vez: sin `DATABASE_URL` sigue el almacén de archivos de siempre; con
  `DATABASE_URL`, `SqlInspectionRepository`.
- La tabla `inspections` guarda el payload completo en `jsonb` y **un solo PNG**:
  el original. El overlay y las capas no viajan a la base; se regeneran con el
  mismo pipeline cuando alguien pide `/media/<id>-result.png` o
  `-layer-<clave>.png`. Las URLs publicadas son idénticas a las de antes, así
  que el frontend y "Guardar HTML" no se enteran.
- Regenerar es legítimo porque el pipeline es determinista: dos corridas de la
  misma imagen dan máscaras idénticas por sha256 (ADR-014, `VALIDACION.md`). Se
  recuerda el último puñado de registros en memoria (`media_cache_size`, 8 por
  defecto) para no recalcular en cada recarga. En modo archivos `/media` sigue
  siendo un `StaticFiles` sobre el disco: ahí no se regenera nada.
- Las columnas tipadas (`created_at`, `method_version`, `app_version`,
  `image_sha256`, `filename`, medidas) son **derivadas** del payload en una
  única función (`_columns`) y nunca se actualizan por separado; el payload es la
  fuente de verdad del contrato.
- Cada registro declara con qué método se midió: `method_fingerprint()`
  (sha256 de los parámetros de `PipelineSettings` más `__version__`, 8 hex). El
  informe del lote agrega `method_versions`, porque promediar 0,36 % y 0,60 % de
  eras distintas en un mismo número no significa nada.
- Postgres 16 en Docker para desarrollo (puerto 5433, para no chocar con un 5432
  nativo) y un DSN gestionado en producción (Neon o Supabase con
  `sslmode=require`): un solo dialecto, sin ORM, con `psycopg` y SQL propio en
  `app/db/migrations/`.
- El driver se importa dentro de `app/db/`: sin base configurada, la aplicación
  no necesita `psycopg` instalado ni un servidor levantado.

**Consecuencias aceptadas.** Desarrollar necesita Docker o un Postgres a mano;
los tests de base se saltean solos cuando no hay servidor, con un mensaje que
dice cómo levantarlo. La caché de regeneración es por proceso: en serverless cada
instancia arranca fría y la primera vista de un registro paga ≈ 0,6 s. Sin DSN
el comportamiento es el de hoy, con el disco efímero de ADR-012.

**Alternativas descartadas.** (a) SQLite: resuelve el desarrollo pero no la
demo, y habría que mantener dos dialectos. (b) Guardar los PNG como `bytea`: la
base crece ≈ 4,8 MB por hoja y se pierde el orden y la consulta. (c) Object storage
(S3/R2) para las imágenes: obliga a dos sistemas con dos credenciales para
resolver un problema que el determinismo del pipeline ya resuelve. (d) ORM:
cuatro consultas fijas no lo justifican.

**Reversibilidad.** Con `DATABASE_URL` vacío se vuelve al almacén de archivos sin
cambiar código; para recuperar el almanaque que vivía en la base alcanza con
`SELECT payload FROM inspections` y volver a escribir los artefactos. Nada del
contrato HTTP depende de este ADR salvo el campo `method_versions` del informe y
el estado `database` de `/api/health`.

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

**Vigencia.** Los rasgos de color descritos acá (ExG medio, fracción verde,
fracción de matiz verde) y la ventana fija de 5×5 fueron reemplazados por
ADR-023. El resto de la decisión —envolvente one-class, seis rasgos, tolerancia
de una falta, `422` con el motivo nombrado— sigue vigente.

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
