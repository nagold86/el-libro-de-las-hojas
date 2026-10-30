# El pipeline, paso a paso

Este documento explica **qué hace la aplicación con una foto de hoja**, en el
orden en que lo hace, con el motivo de cada paso. Está escrito para leerse en voz
alta: cada sección es una etapa y se puede contar sola. Los nombres técnicos
(`core/isolation.py`, `render_overlay`) están para ubicarse en el código.

La premisa del rediseño: **la muestra no es la regla**. Las fotos llegan con otra
luz, otra mesa, hojas amarillas, hojas oscuras, sombras y dedos en el borde. El
pipeline no puede suponer que la hoja es verde ni que el fondo es blanco.

---

## Resumen para contar en tres minutos

1. **Recortar la hoja.** Se modela el color del fondo con el borde de la foto y se
   queda con lo que se diferencia de ese fondo. Ese recorte es lo único que se
   analiza: sin fondo, sin mesa, sin dedos.
2. **Preparar dos vistas.** Una vista «canónica» para medir (sin retoques que
   dependan de la escena) y una vista «de presentación» para mirar (con balance
   de blancos y contraste local).
3. **Juzgar la calidad.** Nitidez, píxeles quemados y superficie utilizable. Si la
   foto no sirve, se dice antes de medir.
4. **Comprobar que es una hoja.** Una compuerta que juzga el recorte —color de
   tejido, textura y brillo— y rechaza un cielo, un documento o una pared.
5. **Detectar las nervaduras.** Primero las nervaduras, porque son crestas oscuras
   y si no se marcan antes se confunden con manchas.
6. **Detectar las manchas** con **dos evidencias**: pardeamiento (rojo sobre
   verde) y oscurecimiento (más oscuro que su entorno). El núcleo estricto siembra
   y un umbral bajo recupera el halo, sin atravesar nervaduras.
7. **Medir.** Área afectada, cantidad, tamaño, forma, orientación y densidad de
   nervadura, siempre en píxeles y fracciones, nunca en milímetros.
8. **Separar la clorosis.** El tejido amarillo no es una mancha parda: se mide
   aparte, como pérdida de verde.
9. **Resumir el color y la textura** de la hoja completa.
10. **Dibujar el resultado** para que se lea sin explicación: contorno, número por
    mancha y leyenda.

Todo lo anterior es **determinista**: la misma foto con los mismos umbrales da
siempre el mismo número. Y cada corrida deja su **huella de método**, para que un
informe no promedie criterios distintos.

---

## Paso 0. Entrada: la foto y su formato

Se acepta PNG o JPEG hasta el límite configurado. El archivo se decodifica, se
normaliza a RGB de 8 bits y se corrige la orientación EXIF. **La foto original se
guarda tal cual**: todo lo demás se recalcula a partir de ella, así que un
resultado siempre se puede reproducir.

- Código: `app/uploads.py` (validación), `core/io.py` (lectura y PNG).
- Si el archivo está dañado o no es una imagen: `400 INVALID_FILE`.

---

## Paso 1. Aislar la hoja del fondo (`core/isolation.py`)

**Qué entra:** la foto completa. **Qué sale:** un recorte con la hoja y el fondo
en negro, más una máscara de hoja.

Este paso es el que hace que el resto funcione con fotos distintas. La versión
anterior pedía verde; una hoja clorótica o una mesa de madera quedaban afuera y la
respuesta era «no es una hoja». El criterio nuevo **no pregunta de qué color es la
hoja, sino cuánto se diferencia del fondo** (ADR-020):

1. **Modelo del fondo.** Se toman los píxeles del aro exterior de la imagen (el 3 %
   del lado menor) y se calcula su color mediano en el espacio Lab y su
   dispersión robusta (MAD). El borde es lo único que con seguridad no es hoja,
   así que es la única zona que se usa para describir el fondo.
2. **Distancia al fondo.** Cada píxel recibe una distancia en unidades de esa
   dispersión: `3 / sensibilidad`, acotada a `[1.2, 12]`. Con sensibilidad 1 el
   corte es «tres desviaciones robustas»: un píxel que se separa del fondo lo
   suficiente para no ser ruido de mesa.
3. **Pista de verde como rescate.** En paralelo se calcula el exceso de verde
   `2G − R − B` con saturación y tono foliar. No decide sola: se **suma** a la
   distancia, para rescatar hojas que se parecen al fondo. Una mesa parda puede
   caer en el rango de tono, así que nunca alcanza por sí sola.
4. **Tres descartes.** Se eliminan los componentes con menos de `max(64, 0.05 %)`
   píxeles del cuadro (grano), los que tocan el borde (son continuidad del fondo,
   salvo que ocupen casi todo el cuadro) y los que **no tienen cuerpo**: el radio
   del disco más grande que cabe dentro del objeto debe superar el 2,5 % del lado
   menor. Ese último filtro es el que distingue una hoja de una línea de texto,
   un cable o el borde de la mesa.
5. **Refinado.** Del componente mayor, GrabCut ajusta el borde por color local con
   un trimapa construido por erosión y dilatación de la región candidata.
6. **Cierre.** Se rellenan los huecos interiores (una mancha oscura no es un
   agujero), se recorta con un 2 % de margen y se pinta el fondo de negro.

**Qué se ve:** cuatro capas —`Candidatos de hoja`, `Distancia al fondo`, `Máscara
de hoja` y `Recorte de la hoja`— para poder discutir el recorte.

**Cuándo falla:** si la hoja y el fondo tienen el mismo color y la hoja no es
verde, no hay contraste que medir. Se puede bajar `Sensibilidad del recorte` en el
panel de umbrales. Si la hoja ocupa casi todo el cuadro (≥ 97 %) no se recorta:
recortar comería nervaduras y bordes.

---

## Paso 2. Preparar dos vistas (`core/preprocess.py`)

Hay dos imágenes que conviven y **no son la misma a propósito** (ADR-013):

- **Vista canónica (para medir).** Solo un filtro bilateral, que quita ruido sin
  borrar bordes. Nada de balance de blancos ni de contraste local: si el método de
  medición dependiera de estadísticas de la escena, dos fotos de la misma hoja con
  luces distintas medirían cosas distintas.
- **Vista de presentación (para mirar).** Balance de blancos (gris de mundo) más
  CLAHE, que realza el contraste local. Se usa para la capa visual y para juzgar
  la nitidez, porque es la imagen con la que se calibraron esos umbrales.

La máscara de píxeles válidos excluye lo saturado (blanco quemado y negro puro),
donde ningún color es confiable.

---

## Paso 3. Calidad (`core/quality.py`)

**Qué se juzga:** nitidez (varianza del laplaciano), fracción de píxeles quemados
o negros y fracción de superficie válida.

Si la foto está borrosa o más de una quinta parte de la hoja está quemada, la
respuesta es `422 IMAGE_UNUSABLE` con el motivo (`borrosa`, `sobreexpuesta`,
`poca_superficie`). Es mejor decir «esta foto no sirve» que devolver números de
una foto que no se puede medir. `Nitidez mínima` está en el panel de umbrales.

---

## Paso 4. Compuerta de dominio (`core/domain.py`)

**Qué se juzga:** el recorte del paso 1, no la foto entera. Cuando la imagen llega
acá el fondo ya se fue y lo que queda debería ser hoja, así que la pregunta no es
«¿hay verde en la foto?» sino «¿esto tiene aspecto de tejido de hoja?». Se miden
seis rasgos, se cuenta cuántos quedan fuera de su rango y, si hay más faltas que
`Faltas toleradas` (una por defecto), la respuesta es `422 IMAGE_NOT_A_LEAF` con
el motivo y el número que lo provocó.

Los rasgos:

1. **Tejido de hoja.** Fracción del recorte con matiz y croma de tejido vegetal,
   del ocre al verde. Es a propósito una familia y no un color: una hoja sana, una
   clorótica y una curada son el mismo producto en distinto punto de secado
   (ADR-023).
2. **Brillo.** Fracción de píxeles casi blancos. Una hoja no es una lámpara.
3. **Textura.** Varianza local en ventana chica, con piso y techo: la pared es
   lisa y el ruido de sensor no imita el tejido. Se mide siempre a 600 px del lado
   menor, así una foto de 165 px y una de 1800 px se juzgan con la misma vara; sin
   eso la resolución del archivo decidía el veredicto.
4. **Entropía.** Bits de detalle, también con piso y techo: una superficie plana no
   tiene nervaduras ni lesiones que medir, y el ruido no es una hoja.

**Qué cambió respecto del verde.** La versión anterior pedía tres cosas de color a
la vez —exceso de verde, superficie verde y matiz verde— que se cumplen o se
incumplen juntas. Una hoja seca fallaba las tres de golpe y se rechazaba por no
ser verde, que es justo el producto que se clasifica. Hoy el color es un solo
rasgo de familia y el peso del rechazo quedó en la textura.

**Cuándo falla:** si el recorte es una superficie lisa y sin croma —una pared, un
cielo limpio— o si está quemado. Los siete valores de la compuerta están en el
panel de umbrales, grupo «compuerta»: cuando una hoja legítima queda afuera, el
mensaje del `422` dice qué rasgo falló y con cuánto, y se corrige ahí.

Es una compuerta explicable, no un clasificador entrenado (ADR-002 y ADR-008).

---

## Paso 5. Nervaduras (`core/segmentation.py`, clase `VeinEnhancer`)

**Por qué antes que las manchas:** una nervadura es una cresta —clara u oscura
según la luz— y sin marcarla primero, la evidencia de oscurecimiento del paso 6
marcaría toda la red como lesión.

Cómo se detectan:

1. Se trabaja sobre el canal verde, que es el que más separa el tejido de la red.
2. **Sombrero negro** (cresta oscura) y **sombrero blanco** (cresta clara) con un
   elemento estructurante elíptico. Se toman los dos: una foto con luz de frente
   invierte la polaridad de la nervadura.
3. **Dos escalas:** el kernel de `Grosor de nervadura` y su mitad. Con un solo
   tamaño, o se pierden las venas finas o se engordan las gruesas.
4. Umbral por **percentil** de la respuesta sobre la superficie válida
   (`Sensibilidad de nervaduras`, 97 por defecto): se queda con el 3 % de píxeles
   de mayor respuesta.
5. **Filtro de forma.** Se descartan los componentes que no parecen una cresta
   (área chica y sin alargamiento). Eso quita grano y esquinas que, si no, cortan
   el crecimiento de una mancha real.

Las nervaduras no se suman a la lesión: se **restan** del camino de las manchas,
dilatadas un píxel, para que su borde no siembre ni deje crecer una mancha.

---

## Paso 6. Manchas (`core/segmentation.py`, clase `LesionSegmenter`)

Una mancha se decide con **dos evidencias complementarias** (ADR-021). Cada una
sola deja familias afuera:

- **Pardeamiento** — `(R − G)/(R + G)` por encima de `Pardeamiento`. Separa el
  tejido oxidado del verde sano y es invariante a la luz. Falla en la necrosis
  negra, donde `R ≈ G`.
- **Oscurecimiento** — cuánto más oscuro es un píxel que su entorno: se compara
  la luminancia Lab con dos desenfoques gaussianos (fino y grueso) y se toma el
  **mínimo** de los dos cocientes, así una sombra suave —que se mueve con su
  entorno— no entra. Además se compara con la mediana del tejido sano, pero solo
  donde el píxel es acromático o pardo: una sombra conserva el matiz verde de la
  hoja. Falla con las manchas casi blancas.

Después, la forma:

1. **Unión y limpieza.** `pardeamiento ∪ oscurecimiento` dentro de la superficie
   válida, apertura 5×5 (borra trazos de un píxel) y cierre 5×5 (une manchas
   partidas).
2. **Filtro por área y forma.** Se descartan los componentes menores al
   `Área mínima de una mancha` o con compacidad por debajo de 0,15: una línea fina
   no es una mancha. Los conservados son las **semillas**.
3. **Histéresis** (ADR-014). El umbral estricto decide qué manchas **existen**; un
   umbral bajo, calculado sobre el tejido sano de **esta** hoja (la mediana del
   pardeamiento sano), recupera el halo pálido que rodea a cada semilla. El
   crecimiento es geodésico y tiene dos topes: `Halo que se recupera` píxeles de
   profundidad y la frontera de las nervaduras. Nunca inventa una mancha donde no
   había semilla.

**Qué se ve:** puntaje de rojo, puntaje de oscurecimiento, umbral crudo, limpieza
morfológica, componentes conservados y descartados, núcleo contra halo y máscara
final.

---

## Paso 7. Morfometría (`core/morphometry.py`)

Por cada componente de la máscara final: área, perímetro, circularidad,
orientación, Feret máximo y área relativa a la superficie válida. Lo que se
publica por hoja: cantidad de manchas, área afectada (fracción), área media,
Feret máximo, circularidad media, orientación y densidad de nervadura.

**Sin escala física no hay milímetros** (ADR-004): todo se declara en píxeles y
fracciones, y esa limitación se escribe en el informe.

---

## Paso 8. Clorosis (`core/chlorosis.py`)

El tejido amarillo no es una mancha parda: si se sumara, el área afectada se
inflaría. Se mide aparte con un **ángulo de matiz** `b*/(|a*| + b*)`: cerca de 0,63
es verde sano y cerca de 1 es amarillo puro. Por encima de
`Amarillamiento (clorosis)` y con croma suficiente, el píxel cuenta como clorosis.
En el overlay se pinta con trama diagonal para que no tape a la terracota de la
mancha cuando se solapan (ADR-015).

---

## Paso 9. Color y textura (`core/descriptors.py`)

Resumen de apariencia de la hoja completa: media y desviación de Lab, exceso de
verde medio, índice de pardeamiento, entropía de la textura, varianza local,
gradiente medio y diferencia de color entre el tejido y las manchas. Sirve para
comparar hojas y lotes sin depender del conteo de manchas.

---

## Paso 10. El resultado visible (`core/render.py`)

El overlay se dibuja **sobre la hoja recortada**, así que las máscaras y la imagen
coinciden píxel a píxel. Con `annotate=True` agrega lo que la foto no dice sola
(ADR-019):

- **contorno** de 2 px en terracota oscuro en cada mancha;
- **número** por mancha, de la más grande a la más chica, en el punto más profundo
  del componente (no en el centroide, que puede caer fuera de una medialuna);
- **leyenda** abajo a la izquierda con los colores de `mancha`, `nervadura` y
  `clorosis`.

Colores del sistema visual: terracota `#A63E24` (mancha), oro viejo `#C9A227`
(nervadura), miel `#D9A441` (clorosis). La textura original se sigue viendo: las
máscaras se mezclan con opacidad, no se pegan encima.

---

## Los umbrales, y quién mueve qué (`core/tuning.py`)

Dieciséis números se pueden ajustar desde la pantalla, cada uno con su rango, su paso
y una frase que explica qué mueve:

| Grupo | Umbral | Qué mueve |
| --- | --- | --- |
| manchas | Pardeamiento (rojo sobre verde) | Cuánto rojo hace falta para contar tejido oxidado |
| manchas | Oscurecimiento de la mancha | Cuánto más oscuro que su entorno; 0 apaga la segunda evidencia |
| manchas | Área mínima de una mancha | Qué componente es una mancha y no ruido |
| manchas | Halo que se recupera | Cuánto puede crecer una mancha desde su núcleo |
| nervaduras | Sensibilidad de nervaduras | Percentil de la respuesta de crestas |
| nervaduras | Grosor de nervadura | Qué ancho de cresta se busca |
| clorosis | Amarillamiento | A partir de qué matiz el tejido es clorótico |
| aislamiento | Sensibilidad del recorte | Cuánta diferencia con el fondo hace falta |
| calidad | Nitidez mínima | Cuándo una foto es demasiado borrosa |
| compuerta | Tejido de hoja mínimo | Fracción del recorte con color de tejido; bajarlo admite hojas más secas |
| compuerta | Brillo admitido | Fracción de píxeles casi blancos que se tolera |
| compuerta | Textura mínima | Por debajo, el recorte es una superficie lisa |
| compuerta | Textura máxima | Por encima, el recorte es ruido y no tejido |
| compuerta | Entropía mínima | Menos detalle que una mancha plana |
| compuerta | Entropía máxima | Más detalle del que tiene una hoja |
| compuerta | Faltas toleradas | Cuántos rasgos fuera de rango se aceptan antes de rechazar |

Cómo viaja un ajuste (ADR-022):

1. La pantalla pide `GET /api/thresholds` y dibuja el panel con ese catálogo: no
   hay rangos escritos dos veces.
2. Al subir, manda solo los valores movidos en un campo `tuning` (JSON).
3. El servidor valida contra el mismo catálogo (`422 INVALID_THRESHOLDS` si algo
   no cierra), arma un pipeline **para esa corrida** y mide.
4. El registro guarda en `trace.tuning` solo lo movido y en `method_version` la
   huella del método, que cambia con los umbrales. Así el informe del lote avisa
   cuando hay hojas medidas con criterios distintos.
5. «Repetir el análisis» vuelve a mandar la **misma foto original** con los
   umbrales actuales: cada prueba deja su propio registro, y la comparación queda
   en el almanaque.

---

## Mapa de archivos

| Archivo | Etapa |
| --- | --- |
| `app/uploads.py`, `core/io.py` | entrada y formato |
| `core/isolation.py` | paso 1: hoja contra fondo |
| `core/preprocess.py` | paso 2: vista canónica y de presentación |
| `core/quality.py` | paso 3: calidad |
| `core/domain.py` | paso 4: compuerta de dominio |
| `core/segmentation.py` | pasos 5 y 6: nervaduras y manchas |
| `core/morphometry.py` | paso 7: medidas |
| `core/chlorosis.py` | paso 8: amarillamiento |
| `core/descriptors.py` | paso 9: color y textura |
| `core/render.py` | paso 10: overlay anotado |
| `core/tuning.py` | catálogo de umbrales |
| `core/pipeline.py` | composición y huella del método |
| `core/orchestrator.py` | orden de las etapas y errores de dominio |

---

## Glosario mínimo

- **Máscara:** imagen de verdadero/falso del mismo tamaño que la foto; dice qué
  píxeles son de una cosa (hoja, mancha, nervadura).
- **Capa:** una imagen intermedia del pipeline que se publica en la pantalla para
  poder auditar cada decisión.
- **Umbral:** el número que separa «sí» de «no» en un criterio. Moverlo no cambia
  el método, cambia su sensibilidad.
- **Histéresis:** usar dos umbrales, uno estricto para sembrar y uno bajo para
  crecer. Evita que el ruido invente manchas.
- **Huella de método:** código corto que resume versión más umbrales. Dos registros
  con la misma huella se pueden promediar; con distinta, no.
- **Lab:** espacio de color con luminancia (`L`) y dos ejes de color (`a`, `b`).
  Es más estable que RGB cuando cambia la luz.
