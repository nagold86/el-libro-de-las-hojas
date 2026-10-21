# Sistema visual — El Libro de las Hojas

Identidad del producto según **Celebrimbor**. Fuente de verdad de los tokens:
[`frontend/tokens.css`](../frontend/tokens.css). Este documento explica el
porqué y deja medidos los contrastes; si hay discrepancia, manda el CSS.

## 1. Concepto — «La Ventana Redonda»

Un cuaderno de campo abierto en el alféizar de una ventana redonda: la Comarca
afuera a media tarde, la hoja adentro sobre papel crema. La pantalla no imita
una película: imita un **objeto de escritorio junto a una huerta**.

La versión anterior era un libro de pergamino a la luz de una vela. Esta es la
misma libreta de día: la luz entra por la ventana, el papel se ve blanco, el
verde es de colina y el ámbar es de miel, no de oro.

Frase guía: **primero se lee, después se admira**. La calidez enmarca; el dato
manda.

## 2. Principios

1. **Luz de día como tema único.** Fondo crema, superficies casi blancas,
   sombras cortas y cálidas. No hay tema oscuro a medias: se eliminó el bloque
   `prefers-color-scheme: dark` y se declara deuda (ver § 12).
2. **Material, no textura.** Papel, lino, madera clara y salvia se expresan con
   color plano, borde y sombra. Ninguna textura ni ilustración va debajo de
   texto pequeño.
3. **El dato primero.** La métrica ocupa el centro; el ornamento vive en el
   horizonte, en los filetes y en el sello. El ámbar nunca es el color de un
   número.
4. **Jerarquía de cuaderno.** Título de inscripción cálida, cuerpo serif de
   lectura, etiquetas y números en monoespaciada.
5. **Incertidumbre visible.** El sello dice «Analizable» o «Con reservas» con
   palabra y color; nunca color solo. La máscara dudosa se lee con su etiqueta.
6. **Estados completos.** Vacío, cargando, error, resultado y lote se diseñan
   juntos y se verifican juntos.
7. **Un solo sistema.** Todo color, fuente y espaciado sale de un token.

## 3. Paleta

### 3.1 Materiales

| Token | Hex | Uso |
|---|---|---|
| `--cream-50` | `#FFFCF2` | Superficie de panel: la hoja |
| `--cream-100` | `#F7F1E2` | Fondo de página: la mesa |
| `--cream-200` | `#EFE6D0` | Papel hundido: montura de figura, trazas, campos |
| `--cream-300` | `#E3D8BE` | Línea de cuaderno (separadores, bordes internos) |
| `--cream-400` | `#D3C6A6` | Borde de papel de los paneles |
| `--ink-900` | `#2B2417` | Texto principal |
| `--ink-600` | `#4E4433` | Texto secundario |
| `--ink-500` | `#6A5F4B` | Metadatos, unidades, etiquetas |
| `--moss-800` | `#2C4A33` | Acción primaria, anillo de foco |
| `--moss-600` | `#3F6B4A` | Estado sano, filete superior de panel |
| `--moss-300` | `#8FB08C` | Ornamento: colina media, hoja del vacío |
| `--sage-200` | `#DCE6D5` | Huerta: relleno de arrastre |
| `--sage-100` | `#EEF3E7` | Huerta clara: depósito y notas |
| `--honey-800` | `#8A540E` | **Acento de texto**: cejillas, cifras de archivo |
| `--honey-500` | `#D9A441` | Ornamento: pomo del sello, aro del depósito. **Nunca texto** |
| `--honey-200` | `#F3E3BF` | Banda de nota de calidad y de carga |
| `--clay-700` | `#A63E24` | Lesión, error, veredicto con reservas |
| `--clay-200` | `#F8E4D7` | Fondo de aviso |
| `--edge-500` | `#8A7C5E` | Borde de control (inputs, dropzone, botón fantasma) |

El **oro viejo ya no es acento de interfaz**. Sobrevive solo como
`--data-vein` (`#C9A227`), donde codifica nervadura, y como `--honey-800` para
texto cálido con contraste suficiente. El `--honey-500` es ornamento: 2.0:1
sobre crema, nunca se usa para texto ni para el único indicador de un estado.

### 3.2 Contrastes medidos

Calculados con la fórmula de luminancia relativa de WCAG 2.2 sobre los hex
exactos de `tokens.css` (sin estimar). Mínimo exigido: **4.5:1** para texto
normal, **3:1** para componentes y elementos gráficos.

| Combinación | Ratio | Uso | Estado |
|---|---|---|---|
| `--ink-900` sobre `--cream-100` | **13.63:1** | Texto principal en página | AA / AAA |
| `--ink-900` sobre `--cream-50` | **14.96:1** | Texto en panel | AA / AAA |
| `--ink-900` sobre `--cream-200` | **12.36:1** | Texto en zona hundida | AA / AAA |
| `--ink-900` sobre `--sage-100` | **13.61:1** | Texto en notas | AA / AAA |
| `--ink-900` sobre `--sage-200` | **11.94:1** | Texto sobre huerta | AA / AAA |
| `--ink-900` sobre `--honey-200` | **12.10:1** | Banda de calidad | AA / AAA |
| `--ink-900` sobre `--clay-200` | **12.48:1** | Texto de aviso | AA / AAA |
| `--ink-600` sobre `--cream-50` | **9.30:1** | Texto secundario | AA / AAA |
| `--ink-600` sobre `--cream-100` | **8.47:1** | Lede | AA / AAA |
| `--ink-600` sobre `--cream-200` | **7.69:1** | Traza JSON | AA / AAA |
| `--ink-600` sobre `--sage-100` | **8.46:1** | Notas | AA / AAA |
| `--ink-600` sobre `--sage-200` | **7.42:1** | Huerta | AA / AAA |
| `--ink-600` sobre `--honey-200` | **7.53:1** | Nota de calidad / carga | AA / AAA |
| `--ink-500` sobre `--cream-50` | **6.10:1** | Unidades, fechas | AA / AAA |
| `--ink-500` sobre `--cream-100` | **5.56:1** | Metadatos en página | AA |
| `--ink-500` sobre `--cream-200` | **5.04:1** | Botón deshabilitado | AA |
| `--ink-500` sobre `--sage-100` | **5.55:1** | Ayuda del depósito | AA |
| `--ink-500` sobre `--sage-200` | **4.87:1** | Texto hundido en huerta | AA |
| `--moss-600` sobre `--cream-50` | **5.99:1** | Acento verde, sello «ok» | AA |
| `--moss-600` sobre `--cream-100` | **5.46:1** | Cejilla verde | AA |
| `--moss-600` sobre `--sage-200` | **4.78:1** | Verde sobre huerta | AA |
| `--moss-800` sobre `--cream-100` | **8.73:1** | Foco y texto verde oscuro | AA / AAA |
| `--honey-800` sobre `--cream-50` | **6.10:1** | Cejillas sobre panel | AA |
| `--honey-800` sobre `--cream-100` | **5.55:1** | Cejillas en página | AA |
| `--honey-800` sobre `--cream-200` | **5.04:1** | Acento sobre hundido | AA |
| `--honey-800` sobre `--sage-200` | **4.86:1** | Acento sobre huerta | AA |
| `--clay-700` sobre `--cream-50` | **6.13:1** | Error / sello con reservas | AA |
| `--clay-700` sobre `--cream-100` | **5.59:1** | Error en página | AA |
| `--clay-700` sobre `--sage-200` | **4.89:1** | Terracota sobre huerta | AA |
| `--clay-700` sobre `--clay-200` | **5.12:1** | «No se pudo completar» | AA |
| `--button-text` sobre `--button-bg` | **9.59:1** | Botón primario | AA / AAA |
| `--cream-50` sobre `--clay-700` | **6.13:1** | Botón de eliminar en hover | AA |
| `--edge-500` sobre `--cream-100` | **3.63:1** | Borde de control | No-texto AA |
| `--edge-500` sobre `--cream-200` | **3.30:1** | Borde de control sobre hundido | No-texto AA |
| `--moss-800` vs `--cream-50/100/sage-100` | **9.59 / 8.73 / 8.72:1** | Anillo de foco | No-texto AAA |
| `--data-vein` sobre `--cream-50` | **2.36:1** | Muestra de leyenda | solo dato + borde `--edge-500` |
| `--honey-500` sobre `--cream-100` | **2.00:1** | Ornamento | decorativo |

Notas de honestidad visual:

- `--surface` y `--page` tienen 1.10:1 entre sí: **el panel no se separa del
  fondo por valor**. Se separa por el filete superior de 3 px, el borde de papel
  (1.50:1, decorativo) y la sombra. Ningún texto depende de esa diferencia.
- `--line-paper` a 1.50:1 es borde decorativo; los bordes que **sí** delimitan
  un control usan `--edge-500` (≥3:1).
- El filete de 3 px `--moss-600` de cada panel es refuerzo de marca; el
  agrupamiento ya lo dice el `h2` y el espaciado.

### 3.3 Datos

| Token | Hex | Uso |
|---|---|---|
| `--data-healthy` | `#3F6B4A` | Serie sana, veredicto positivo |
| `--data-lesion` | `#A63E24` | Máscara de lesión; **coincide con `core/render.py`** |
| `--data-lesion-edge` | `#7A1F14` | Contorno de lesión en el overlay |
| `--data-vein` | `#C9A227` | Nervadura |
| `--data-series-1` | `#3F6B4A` | Categórica 1 (musgo) |
| `--data-series-2` | `#8A540E` | Categórica 2 (miel oscura) |
| `--data-series-3` | `#A63E24` | Categórica 3 (terracota) |
| `--data-series-4` | `#3F5568` | Categórica 4 (pizarra) — 7.54:1 sobre `--cream-50` |
| `--data-series-5` | `#6B4767` | Categórica 5 (ciruela) — 7.52:1 |
| `--data-series-6` | `#2F6663` | Categórica 6 (laguna) — 6.39:1 |

Orden categórico fijo (nunca cíclico por valor) y **siempre** con etiqueta o
patrón además del color. Las seis series superan 5.9:1 contra `--cream-50`,
pero no todas superan 3:1 entre sí: un gráfico que necesite distinguir dos
series contiguas debe sumar textura o rótulo directo.

## 4. Tipografía

| Rol | Familia | Licencia | Uso |
|---|---|---|---|
| Display | **Fraunces** | SIL OFL 1.1 | Título, nombres de panel, sello, depósito |
| Cuerpo | **Alegreya** | SIL OFL 1.1 | Texto corrido, formularios, leyendas |
| Datos | **IBM Plex Mono** | SIL OFL 1.1 | Métricas, ids, fechas, unidades, cejillas |

- Fraunces entra en peso 600 y tamaño óptico automático. Tiene carácter cálido
  y curvas de imprenta: reemplaza a Cinzel, que era inscripción romana.
- Alegreya a 17 px con línea 1.62 y medida máxima de 62 caracteres. Su
  x-height alta sostiene la lectura en pantalla mejor que un Garamond a este
  tamaño.
- IBM Plex Mono para todo número: cifras tabulares, alineadas, con unidad
  declarada al lado.
- Fallbacks declarados en los tokens (`Iowan Old Style`, Georgia, Consolas).
  Si Google Fonts no carga, la pantalla conserva jerarquía y contraste; solo
  pierde el matiz.

Escala: `--text-2xs .75rem` · `--text-xs .8125rem` · `--text-sm .9375rem` ·
`--text-base 1.0625rem` · `--text-lg 1.1875rem` · `--text-xl 1.5rem` ·
`--text-2xl 1.875rem` · `--text-3xl clamp(2.15rem, 4vw, 2.9rem)`.

Ninguna palabra en display dentro de párrafos. Ninguna versalita decorativa en
cuerpos de texto pequeños (solo en `dt` de las notas, a 17 px).

## 5. Espaciado, forma y luz

- Base 4 px: `--space-1` a `--space-10` (0.25 → 5 rem). Todo `padding`,
  `margin`, `gap` y separación usa estos tokens.
- Radios: `--radius-sm 3px` (fichas y campos), `--radius-md 10px` (panel),
  `--radius-lg 18px` (depósito), `--radius-full` (sello, chip).
- Trazos: `--border-1`, `--border-2`, `--border-rail 3px` (filete de panel).
- Sombra única y corta, `--shadow-card`: dos capas, tinte cálido, sin brillo.
  Es la sombra de una hoja sobre una mesa, no un resplandor.
- Ancho de lectura `--measure 62ch`; app 1180 px; columna lateral 320 px.
- Objetivo táctil `--size-touch 44px` en botones, filas del archivo y borrado.
- Los pocos px que quedan en `styles.css` son geometría —breakpoints de 920 y
  560 px, tamaño del resplandor de cielo, alto de la traza—, nunca espaciado.

## 6. Estructura de la pantalla

```
┌────────────────────────────────────────────────────────────────┐
│  FELLOWSHIP · VISIÓN CLÁSICA              [servicio en línea]  │
│  El Libro de las Hojas                                         │
│  Cuaderno de campo de la Comarca…                              │
├────────────────────────────────────────────────────────────────┤
│  colinas · seto · puerta redonda  (banda decorativa 110–168 px)│
├─────────────────────────────────┬──────────────────────────────┤
│  En la mesa / Depósito          │  Almanaque / Archivo         │
│  ┌───────────────────────────┐  │  ◦ 3 inspecciones            │
│  │  brote · borde punteado   │  │  ◦ IMG_…_14  · 0,8 %         │
│  │  [Elegir imagen]          │  │  ◦ IMG_…_15  · 0,2 %         │
│  └───────────────────────────┘  │                              │
│  (aviso / carga)                │  Cómo leer las medidas       │
│  La inspección / Resultado      │  (fichas de notas)           │
│  [sello redondo]  Medidas ▢▢▢   │                              │
│  Overlay  [imagen sobre cartón] │                              │
└─────────────────────────────────┴──────────────────────────────┘
```

En móvil (360 px) se apila: cabecera → colinas → depósito → resultado →
archivo → notas. El sello baja de 132 a 120 px y el nombre de archivo se parte
en varias líneas sin desbordar.

## 7. Componentes

- **Sello de calidad**: puerta redonda de 132 px (120 en móvil), doble anillo en
  `currentColor`, pomo de miel en el borde. Verde musgo para «Analizable»,
  terracota para «Con reservas». Siempre con la palabra; el color acompaña.
- **Horizonte**: banda SVG original de tres colinas y una puerta redonda, al
  final de la cabecera. Es decoración `aria-hidden`, sin texto encima y sin
  assets de la franquicia. Se recorta por el centro en pantallas angostas.
- **Depósito**: zona salvia con borde punteado de 2 px `--edge-500` (3.3:1),
  brote dibujado a mano en SVG, título en display y un botón primario. Acepta
  clic, arrastre y teclado mediante el botón visible.
- **Ficha de métrica**: etiqueta mono en versalita, valor mono grande, unidad
  mono pequeña. Fondo `--cream-100` sobre el panel para separar sin sombra.
- **Overlay**: figura montada sobre cartón `--cream-200` con 8 px de margen,
  leyenda de dos entradas (lesión y nervadura) y pie con los parámetros.
- **Archivo (lote)**: cuenta en chip, filas con miniatura de 48 px, nombre,
  fecha y porcentaje; la fila activa se marca con fondo salvia y barra musgo de
  3 px. Borrar mide 44×44 px.
- **Aviso de error**: banda terracota con borde izquierdo de 3 px, `role="alert"`
  y texto accionable con el código entre paréntesis.
- **Nota de calidad**: banda de miel con borde izquierdo cálido. Es neutra: no
  afirma que la hoja sea buena, solo presenta las advertencias. El veredicto
  vive en el sello.
- **Vacío**: hoja dibujada con CSS (dos esquinas redondeadas) y frase
  «La huerta espera su primera hoja».
- **Diálogo**: hoja sobre fondo oscurecido al 50 %, botones de 44 px.

### Contrato de estados con `app.js`

| Estado | Disparador real en `app.js` | Cómo se ve |
|---|---|---|
| Vacío | `#ledger-empty.hidden = false`, contador «sin inspecciones» | `.empty` con hoja y frase; nada más ocupa el archivo |
| Cargando | `setBusy(true)` → `#status` visible, `aria-busy="true"` en `#dropzone`, `body[data-busy]`, `#pick.disabled` | Banda miel con punto musgo pulsante, dropzone con borde sólido y botón deshabilitado |
| Error | `showError()` → `#alert.hidden = false` | Banda terracota con `role="alert"` y mensaje |
| Resultado | `renderResult()` → `#result.hidden = false` | Sello, nota de calidad, medidas, overlay, traza |
| Lote | `renderLedger(items)` con n ≥ 1 | Chip de cuenta + filas del archivo + fila activa |

No hay un sexto hook: el «lote» es el archivo poblado. La pantalla no cambia de
vista para mostrarlo.

## 8. Overlay de máscaras (`core/render.py`)

| Elemento | Color | Mezcla | Token |
|---|---|---|---|
| Lesión | `#A63E24` | 55 % | `--data-lesion` |
| Contorno de lesión | `#7A1F14` | 85 % (1 px) | `--data-lesion-edge` |
| Nervadura | `#C9A227` | 35 % | `--data-vein` |

- El 45 % del píxel original sobrevive dentro de la lesión: **la textura de la
  hoja no se tapa**. No se pinta el fondo sano ni se satura el verde.
- La lesión cambió de `#B4462F` a `#A63E24`: es la misma familia terracota que
  el error de interfaz, así el rojo del dato y el rojo del aviso son uno solo.
  Se verificó en dos hojas de `imgs/` (verde medio y verde amarillento): la
  mancha terracota y su contorno oscuro se leen sobre ambas.
- La nervadura sigue en oro viejo. **Límite medido**: sobre hojas
  amarillo-verdosas el oro se acerca al color del limbo y pierde separación. El
  overlay de nervadura es opcional por contrato («solo si aporta lectura»); si
  Legolas o Gimli piden más, la corrección es un `--data-vein` más oscuro y un
  cambio de una palabra en el `alt` de `app.js` (dueño: Aragorn), no un ajuste
  local de pantalla.
- El PNG se sirve sin pérdida y en la resolución de entrada.

## 9. Movimiento

- Transiciones de 180 ms `ease-out` solo en color, borde, fondo y sombra.
- Única animación: el punto de estado late a 1.4 s entre opacidad 1 y 0.45
  mientras se analiza; nunca desaparece.
- Sin parallax, sin brillos, sin movimiento de fondo, sin animación de las
  colinas.
- `prefers-reduced-motion: reduce` lleva `--transition` a 0 ms, desactiva el
  pulso y vuelve el scroll instantáneo.

## 10. Accesibilidad

- Texto normal ≥ 4.5:1, componentes ≥ 3:1, medido en § 3.2.
- Foco: anillo de 2 px `--moss-800`, separado 2 px del control. El hueco
  muestra la página y garantiza el contraste aun sobre botones oscuros.
- Objetivos táctiles de 44×44 px: botón primario, fantasma, peligro, actualizar
  y borrar. El chip de estado no es interactivo.
- El depósito no es un botón falso: el foco de teclado entra por `#pick` y el
  `input` oculto queda con `tabindex="-1"` para no crear una parada invisible.
- `#status` y `#live` son regiones `aria-live="polite"`; `#alert` es
  `role="alert"`. El foco no se mueve solo.
- Cada número de pantalla declara su unidad en `.metric-unit`: fracción de
  superficie, componentes, píxeles, rango 0–1, varianza del laplaciano. El
  formateo y la unidad vienen del contrato; el diseño no los inventa.
- La app funciona a 200 % de zoom y a 360 px sin scroll horizontal.
- Nada de textura ni imagen bajo texto pequeño: el horizonte está aislado y el
  papel es color plano.

**Checklist de entrega** (la audita Boromir):

1. Vacío, cargando, error, resultado y lote capturados a 360 px y 1180 px.
2. Contraste medido contra los hex de `tokens.css`, no estimado.
3. Unidad declarada en cada número visible.
4. Overlay legible sobre hoja verde media y hoja verde amarillenta.
5. Cero colores, fuentes o espaciados literales en `styles.css`.
6. Cero assets, logos, inscripciones o mapas de la franquicia.
7. Foco visible en todos los interactivos, probado solo con teclado.
8. Sin tema oscuro activo: `color-scheme: light` y sin bloque `dark`.

## 11. Contrato con `frontend/app.js`

La pantalla conserva **todos** los ids que consulta `app.js`; el informe agregó
su propio cableado sin renombrar ninguno:

`health`, `health-text`, `dropzone`, `pick`, `file-input`, `drop-hint`,
`alert`, `alert-message`, `status`, `status-text`, `live`, `result`,
`result-title`, `result-meta`, `seal`, `seal-word`, `verdict-note`, `metrics`,
`overlay`, `trace-json`, `original-link`, `delete-current`, `ledger-list`,
`ledger-count`, `ledger-empty`, `refresh`, `clear-archive`, `confirm-delete`,
`confirm-title`, `confirm-text`, `confirm-accept`.

Clases y atributos que `app.js` crea o consulta:

- `#seal` recibe `className = "seal seal--ok" | "seal seal--warn"`: por eso el
  sello **no** lleva clases extra en el HTML y todo su estilo vive en `.seal`.
- `.metric`, `.metric-label`, `.metric-value`, `.metric-unit`.
- `.ledger-item`, `.ledger-load` (con `data-id`), `.ledger-text`,
  `.ledger-delete` (con `data-id` y `data-name`), `aria-current="true"`.
- `.is-dragover` en `#dropzone`; `aria-busy`; `body[data-busy]`.
- `data-state` en `#health` con valores `pending`, `ok`, `down`.
- `hidden` en `#alert`, `#status`, `#result`, `#ledger-empty`.
- `#file-input` conserva `id` y `accept`; solo se le agregó `tabindex="-1"` y
  `aria-label` (no los consulta `app.js`).

El `alt` del overlay lo escribe `app.js` con las palabras «óxido» y «oro». Por
eso la lesión sigue siendo un óxido de hierro (terracota) y la nervadura sigue
siendo oro: el texto alternativo no queda mintiendo. Si más adelante se cambia
la nervadura, hay que pedirle a Aragorn ese cambio de palabra.

## 12. Deuda declarada

1. **Tema oscuro**: eliminado, no reemplazado. Si el producto lo necesita, se
   construye como conjunto completo y AA desde los mismos tokens (fondo,
   superficie, texto, líneas, foco, datos y overlay), no como un parche. Hasta
   entonces `color-scheme: light` evita controles nativos ilegibles.
2. **Nervadura sobre hoja amarilla**: el oro pierde separación. Requiere
   `--data-vein` más oscuro y un cambio de una palabra en el `alt` de `app.js`.
3. **Tipografías remotas**: Fraunces, Alegreya e IBM Plex Mono se cargan desde
   Google Fonts. Sin red se usan los fallbacks del sistema; el auto-alojamiento
   queda pendiente para que la identidad no dependa de terceros.
4. **Pasada de navegador parcial**: hay capturas headless con Edge a 1280 px
   (vacío, resultado, error) y a 360 px (resultado) en `sandbox/capturas/`;
   faltan el estado de carga, el error a 360 px, 200 % de zoom y la prueba
   solo con teclado.
5. **Series categóricas**: no todas las parejas llegan a 3:1 entre sí; los
   gráficos deben sumar textura o rótulo directo.
6. **Pomo del sello**: es ornamento CSS. No debe convertirse en control ni
   recibir interacción sin un rediseño del componente.
7. **Nombre de archivo en móvil**: `#result-title` parte el nombre en dos
   líneas (`…_1` / `4.png`). No desborda ni pierde información, pero la
   lectura es fea; si molesta, se acorta a un identificador de registro.

## 13. Límites legales y de marca

La inspiración es **material y atmósfera**: papel, lino, madera clara, salvia,
miel y colinas. No se usan logos, la inscripción del Anillo, el ojo de Sauron,
mapas ni fotogramas de las películas. El horizonte, el brote, la puerta y la
hoja del vacío son SVG originales de este proyecto, dibujados con trazos
simples. Las tres familias tipográficas son SIL Open Font License 1.1.

---

## 14. Informe del lote — «La página del almanaque»

El informe no es una pantalla nueva: es una página que se desprende del
Almanaque. Se abre desde `#report-open`, en el panel «Archivo», y vive en un
`<dialog id="lot-report">`. Esta sección fija la forma; el cableado de datos es
de Aragorn.

### 14.1 Concepto

Una página arrancada del cuaderno: papel crema, filetes de tinta, un sello de
nivel y gráficos dibujados con trazo. La lectura baja en un solo orden:

**qué se midió → cuánto → cómo se reparte → qué hoja mirar → la tabla.**

No hay tarjetas flotantes, ni sombra grande, ni `dark mode`, ni neón. La
separación entre secciones la hacen un filete y el espaciado, no una caja.

### 14.2 Estructura

```
<dialog id="lot-report">                         hoja máxima 1120 × 92dvh
└─ form.report-sheet  (method="dialog")          papel crema, scroll interno
   ├─ header.report-head                         filete musgo 3px + tinta 2px
   │  ├─ cejilla · h2 «Informe del lote» · #report-subtitle
   │  ├─ .report-seal #report-seal               nivel operativo dominante
   │  ├─ #report-severe                          aviso si hay hojas severas
   │  └─ .report-actions [#report-print] [#report-close]
   ├─ .report-states [#report-empty] [#report-loading] [#report-error]
   └─ #report-body                               oculto hasta tener datos
      ├─ Cifras del lote (4 fichas con unidad)
      ├─ Distribución por nivel (banda + 4 sellos con conteo)
      ├─ Gráfico 1 · histograma (#report-histogram)
      ├─ Gráfico 2 · dispersión (#report-scatter)
      ├─ Gráfico 3 · ranking (#report-ranking)
      ├─ Tabla del lote (#report-rows)
      └─ Notas del lote (#report-quality, #report-methods)
```

Cerrar con el botón usa `form method="dialog"`; Escape lo cierra de forma
nativa. El clic en el backdrop no se cablea, igual que en `#confirm-delete`.
El botón Imprimir es `type="button"` para no cerrar el diálogo.

### 14.3 Tokens nuevos

Todos viven en `tokens.css`; `styles.css` no declara ningún color, fuente ni
espaciado literal.

| Token | Valor | Uso |
|---|---|---|
| `--report-sheet` | `var(--cream-50)` | Papel del informe |
| `--report-rule` | `var(--ink-900)` | Filete principal de cabecera y tablas |
| `--report-rule-soft` | `var(--line-paper)` | Filetes internos y títulos de sección |
| `--report-width` | `1120px` | Ancho máximo de la hoja |
| `--report-height` | `92dvh` | Alto máximo del diálogo |
| `--report-seal-size` | `112px` | Sello de nivel |
| `--report-figure-min` | `190px` | Ancho mínimo de una cifra |
| `--chart-height` | `268px` | Reserva del gráfico antes de insertar el SVG |
| `--chart-height-sm` | `196px` | Ranking y móvil |
| `--chart-axis` | `var(--ink-500)` | Rótulos de ejes y ticks |
| `--chart-grid` | `var(--cream-300)` | Retícula |
| `--chart-baseline` | `var(--ink-900)` | Línea base |
| `--chart-bar` | `var(--data-series-3)` | Barras: terracota de lesión |
| `--severity-sano` | `var(--data-series-1)` | Musgo |
| `--severity-leve` | `var(--data-series-2)` | Miel oscura |
| `--severity-moderado` | `var(--data-series-3)` | Terracota |
| `--severity-severo` | `var(--data-series-3)` | Terracota + trama cruzada |
| `--print-margin` | `14mm` | Margen de página impresa |

No se agregó ningún color nuevo: los cuatro niveles usan las series de datos
existentes. Moderado y severo comparten terracota; se separan por **trama,
palabra, forma del punto y filete**, nunca por color solo.

### 14.4 Componentes

- **Botón Informe** (`.icon-button--strong`): 44 px, mono en versalita, acento
  miel oscura; comparte fila con «Actualizar» dentro de `.panel-tools`.
- **Diálogo** (`.report-dialog`): ancho `min(100% − 2·space-6, 1120px)`, alto
  máximo 92dvh, borde de papel de 1 px, sin sombra grande. El scroll ocurre en
  `.report-sheet`, no en la página.
- **Cabecera**: filete superior de 3 px musgo (marca) y filete inferior de 2 px
  tinta (cuaderno). Título en Fraunces; subtítulo y cejilla en mono.
- **Sello de nivel** (`#report-seal[data-level]`): doble anillo de 112 px, pomo
  de miel heredado del sello de calidad. Palabra en display y «nivel
  operativo» en mono. `sin_datos` usa `--text-muted`; `severo` cambia a doble
  anillo grueso. El color acompaña; la palabra decide.
- **Aviso de severas** (`#report-severe`): banda terracota con filete izquierdo
  de 3 px, visible solo si `has_severe`. Texto: «Hay hojas severas».
- **Cifras**: cuatro fichas sin caja, con filete superior de 2 px tinta. Valor
  en mono `--text-2xl`; unidad siempre visible. La peor hoja trunca el nombre
  con `text-overflow: ellipsis` y el JS debe dejar el nombre completo en
  `title`.
- **Banda de niveles**: segmentos proporcionales con trama. Es `aria-hidden`;
  los datos los llevan los cuatro sellos de abajo.
- **Sellos de nivel**: cuatro bloques con trama superior, etiqueta directa,
  conteo en mono, porcentaje y corte operativo. Las tramas son horizontales
  (sano), verticales (leve), diagonales (moderado) y cruzadas (severo).
- **Tabla del lote**: filete de tinta en el encabezado, filas de 44 px con
  botón `.report-open` y `data-id`. En ≤ 720 px se convierte en filas
  etiquetadas (`td[data-label]`); sin scroll horizontal.
- **Estados**: vacío punteado, carga en miel con punto musgo y error en
  terracota con `role="alert"`.

### 14.5 Gráficos: especificación para el JS

Los tres contenedores están vacíos en el HTML y llevan `role="img"` con una
etiqueta base que el JS debe completar con el resumen real. El CSS ya define
tipografía, retícula, línea base, barras y puntos.

#### Gráfico 1 — Histograma (`#report-histogram`)

- `viewBox="0 0 720 268"`, `preserveAspectRatio="xMidYMid meet"`, ancho 100 %.
- Márgenes: izquierda 52, derecha 16, arriba 24, abajo 48. Área de trazo:
  652 × 196.
- X categórica: seis intervalos `0–1 %`, `1–2 %`, `2–5 %`, `5–10 %`,
  `10–20 %`, `≥ 20 %` de superficie afectada. Y: hojas (n), de 0 al máximo,
  con 4 divisiones y enteros.
- Barras: clase `.chart-bar` (terracota). Conteo encima en `.chart-value`;
  ticks en `.chart-tick`; títulos de eje en `.chart-axis-title`; retícula
  `.chart-grid`; base `.chart-baseline`.
- Etiqueta accesible: «Histograma de n hojas; el intervalo más poblado es …».
- Tabla alternativa: `#report-histogram-data` (Intervalo · Hojas).

#### Gráfico 2 — Dispersión (`#report-scatter`)

- `viewBox="0 0 720 340"`. Márgenes: izquierda 56, derecha 24, arriba 24,
  abajo 56.
- X: `lesion_count` (componentes) desde 0. Y: `area_fraction` convertida a %
  de superficie válida, desde 0 con 5 % de aire arriba.
- Un punto fijo por hoja (radio 4). **El tamaño no codifica el Feret máximo**:
  se declara el límite en el texto y el Feret vive en la tabla.
- Clases de punto: `.chart-point--sano` (círculo musgo),
  `.chart-point--leve` (círculo miel), `.chart-point--moderado` (círculo
  terracota), `.chart-point--severo` (rombo terracota con contorno de tinta).
- Leyenda en HTML con las mismas formas; la palabra «Severo (rombo)» evita
  depender del color.
- Etiqueta accesible con n y rango; tabla `#report-scatter-data`
  (Hoja · Lesiones · Área · Nivel).

#### Gráfico 3 — Ranking (`#report-ranking`)

- `viewBox="0 0 720 H"`, con `H = 40 + 34 · n` para hasta cinco hojas `worst`.
- Márgenes: izquierda 190 (nombre), derecha 64 (valor), arriba 12, abajo 36.
- Barras horizontales de 18 px, una por hoja, ordenadas de mayor a menor
  `area_fraction`. Nombre truncado a 26 caracteres con `<title>` completo;
  valor en `.chart-value` al final de la barra.
- Barras `.chart-bar`; la peor hoja puede llevar `.chart-bar--worst`.
- Etiqueta accesible con la peor hoja y su %; tabla
  `#report-ranking-data` (Hoja · Área · Nivel).

Los tres SVG usan `font-family: var(--font-mono)` por CSS; ningún texto del
gráfico baja de `--text-2xs` (12 px). El contenedor reserva `--chart-height`
para que el diálogo no salte al insertar el SVG.

### 14.6 Contraste y accesibilidad del informe

Medido sobre los hex de `tokens.css` (WCAG 2.2):

| Combinación | Ratio | Uso | Estado |
|---|---|---|---|
| `--ink-900` sobre `--report-sheet` | **14.96:1** | Título, cifras, tabla | AA / AAA |
| `--ink-600` sobre `--report-sheet` | **9.30:1** | Notas y leyendas | AA / AAA |
| `--ink-500` sobre `--report-sheet` | **6.10:1** | Ejes, unidades, cortes | AA |
| `--severity-sano` sobre `--report-sheet` | **5.99:1** | Sello y rótulo sano | AA |
| `--severity-leve` sobre `--report-sheet` | **6.10:1** | Sello y rótulo leve | AA |
| `--severity-moderado` / `--severity-severo` sobre `--report-sheet` | **6.13:1** | Sello y rótulo terracota | AA |
| `--ink-900` sobre `--honey-200` | **12.10:1** | Carga | AA / AAA |
| `--clay-700` sobre `--clay-200` | **5.12:1** | Error | AA |

- Las tramas son refuerzo, no el único indicador: cada nivel tiene palabra,
  conteo y porcentaje visibles.
- El foco de teclado usa el anillo global de 2 px `--moss-800` con 2 px de
  separación; los botones Imprimir y Cerrar miden 44 px.
- El diálogo abre con foco nativo en el primer control y lo devuelve al botón
  Informe al cerrar. `#report-loading` es `role="status"`;
  `#report-error` es `role="alert"`.
- En ≤ 720 px la tabla del lote se lee como filas etiquetadas; no hay scroll
  horizontal. Las cifras pasan a dos columnas y los sellos a dos.
- `prefers-reduced-motion` apaga el pulso de carga y conserva el resto estable.

### 14.7 Contrato con `app.js` (informe)

`app.js` implementa este contrato y lo mantiene separado del panel de
inspección. El JS debe:

1. Abrir `#lot-report` con `showModal()` desde `#report-open`; mostrar
   `#report-loading`, ocultar `#report-body`, `#report-empty` y
   `#report-error`, y pedir `GET /api/reports/lot`.
2. Poblar `#report-subtitle` con fecha de generación y cantidad de imágenes
   aceptadas; el formato de fecha es el de `app.js`.
3. Pintar el sello: `#report-seal.dataset.level = dominant_severity` y
   `#report-seal-word` con la palabra (`Sin datos`, `Sano`, `Leve`,
   `Moderado`, `Severo`). Mostrar `#report-severe` si `has_severe`.
4. Poblar cifras y sellos. `#report-worst-name.title` lleva el nombre completo.
5. Insertar los SVG en `#report-histogram`, `#report-scatter` y
   `#report-ranking`, actualizar su `aria-label` y llenar las tablas
   `#report-histogram-data`, `#report-scatter-data`,
   `#report-ranking-data`.
6. Construir las filas de `#report-rows`: `tr.report-row` con
   `data-severity`; cada `td` con `data-label` (Hoja, Fecha, Lesiones, Área,
   Feret máx., Calidad); números con `.is-number`; primera celda con
   `button.report-open[data-id]` y el nombre de archivo.
7. Poblar `#report-quality` y `#report-methods` con `<li>`; si están vacíos,
   el CSS muestra «Sin registros.».
8. Cablear `#report-print` a `window.print()` y `#report-save` a la copia HTML
   autocontenida (§14.11). El cierre con `#report-close` y Escape es nativo.
9. Gestionar el fetch con `aria-busy` en `#lot-report`; ante fallo, mostrar
   `#report-error` con `#report-error-text`. No inventar cifras: los estados
   sin datos no muestran números.

Ids y clases nuevas: `report-open`, `lot-report`, `report-sheet`,
`report-head`, `report-title`, `report-subtitle`, `report-seal`,
`report-seal-word`, `report-severe`, `report-print`, `report-close`,
`report-empty`, `report-loading`, `report-error`, `report-error-text`,
`report-body`, `report-images`, `report-lesions`, `report-area-median`,
`report-worst-area`, `report-worst-name`, `report-band` + `report-band-<clave>`,
`report-sev-<clave>-count`, `report-sev-<clave>-pct`, `report-histogram`,
`report-histogram-data`, `report-scatter`, `report-scatter-data`,
`report-ranking`, `report-ranking-data`, `report-rows`, `report-quality`,
`report-methods`, `report-save`, `report-save-status`; clases
`.report-section`, `.report-figure`, `.report-seal`,
`.report-warning`, `.report-legend`, `.report-table`, `.report-row`,
`.report-open`, `.is-number`, `.sev--sano|leve|moderado|severo`.

### 14.8 Impresión

- `@media print` oculta masthead, horizonte, layout, footer, skip-link y el
  diálogo de borrado. También oculta `.report-actions` y los `<details>` de
  datos: en papel quedan los gráficos y la tabla del lote.
- El diálogo se vuelve estático, sin borde, sombra ni alto máximo; el informe
  usa todo el ancho y el scroll desaparece.
- **Tipografía estática en papel.** `tokens.css` redefine `--font-display`,
  `--font-body` y `--font-mono` dentro de `@media print` con pilas de respaldo
  (Iowan Old Style/Palatino/Georgia y Consolas). Edge exporta los tipos
  variables de Google como Type 3 y pierde métricas: el PDF mostraba letras
  superpuestas en avisos, epígrafes y tabla. La pantalla conserva Fraunces,
  Alegreya e IBM Plex Mono.
- `print-color-adjust: exact` conserva papel, tramas y sellos. Aun en escala de
  grises, cada nivel conserva palabra y trama.
- `@page A4` con margen `--print-margin` (14 mm). Las cuatro cifras van en una
  sola fila de cuatro columnas; la tabla usa cuerpo xs con padding compacto y
  fechas sin partir; el nombre de la peor hoja se envuelve completo en lugar de
  recortarse. Los títulos de sección no quedan huérfanos
  (`break-after: avoid`), y las secciones con gráfico y las notas no se cortan
  (`break-inside: avoid`). El `thead` de la tabla se repite por página.
- El backdrop no se imprime y el pie de impresión
  (`.report-print-note`) solo aparece en papel.
- Verificado con Edge headless (CDP): un lote de 5 hojas produce un PDF A4 de 4
  páginas legible a 200 dpi; la cuarta queda con las notas del lote.

### 14.9 Deuda declarada del informe

1. **Gráficos dependientes de JS**: sin `GET /api/reports/lot` no hay SVG ni
   tablas alternativas; el estado de error es el único respaldo.
2. **Texto alternativo de los gráficos**: lo redacta Aragorn al insertar cada
   SVG; el diseño no puede verificar que describa bien los datos.
3. **Clic en backdrop**: no cableado, por consistencia con el diálogo de
   borrado. Si se agrega, debe hacerse en ambos diálogos.
4. **Impresión probada solo en Edge/Chromium headless**: el PDF A4 de 4 páginas
   con 5 hojas es legible, pero faltan Firefox y la prueba en papel físico. Con
   más hojas el corte de página puede cambiar; la cuarta página ya queda casi
   vacía con solo las notas. `@page` con `var(--print-margin)` puede caer al
   margen por defecto en navegadores viejos.
5. **Tabla móvil**: depende de que el JS escriba `data-label` en cada `td`; sin
   eso las filas quedan sin etiqueta.
6. **Ranking de hasta cinco hojas**: usa `worst`; el lote completo está en la
   tabla. No se grafican las 2000 hojas del dataset.
7. **Feret no codificado en el tamaño del punto**: se declara en el texto y se
   resuelve en la tabla. Si se quisiera codificar, hace falta una escala
   visual y una leyenda de tamaño.
8. **Cortes operativos, no agronómicos**: el informe no diagnostica; el texto
   lo dice en la cejilla del sello, en la distribución y en el colofón.
9. **Sin tema oscuro**: el informe hereda la deuda general (§ 12).
10. **Aviso de severas estático**: si el contrato agrega contexto por hoja, el
    texto cambia en `index.html` sin tocar el JS.
11. **La tipografía de papel no es la de pantalla**: las pilas estáticas evitan
    el defecto Type 3 del exportador, pero el papel pierde Fraunces y Alegreya.

### 14.10 Reglas de formato y cableado fino

- **Área sin símbolo duplicado**: `#report-area-median`, `#report-worst-area`,
  las celdas de la columna «Área (%)» y las tablas de datos reciben **solo el
  número** (por ejemplo `24,1`). El `%` ya está en la unidad o en el encabezado;
  no usar `format.pct` en esos nodos. Para el resto de los porcentajes (sellos
  de nivel, subtítulo) sí vale `format.pct`.
- **Nombre completo**: `#report-worst-name.title` lleva el nombre de archivo
  completo; el recorte visual es solo CSS.
- **Etiquetas móviles exactas** para `td[data-label]`: `Hoja`, `Fecha`,
  `Lesiones`, `Área (%)`, `Feret máx. (px)`, `Calidad / aislamiento`.
- **Botón de fila**: `button.report-open` debe ser `type="button"` y llevar
  `data-id`; sin `type="button"` el submit cierra el `<form method="dialog">`.
- **Columna de calidad**: reúne `quality_flags` (o «sin advertencias») y el
  `isolation_method` del punto; no es una segunda métrica numérica.
- **Banda proporcional**: `#report-band-<clave>` recibe
  `style.flexGrow = String(fraction)`; si el conteo es 0, `hidden = true` para
  no dejar un segmento mínimo. La banda es `aria-hidden`; los sellos son los
  que informan.
- **Reset al abrir**: `#report-seal` vuelve a `sin_datos`, `#report-seal-word`
  a «Sin datos» y `#report-severe` a oculto. Así la carga no muestra el nivel
  del informe anterior.
- **Vacío**: ocultar `#report-loading` y `#report-body`, mostrar
  `#report-empty`. **Error**: ocultar carga y cuerpo, mostrar `#report-error`
  con `#report-error-text`.
- **`aria-busy`**: `#lot-report.setAttribute("aria-busy", "true")` durante el
  fetch y `"false"` al terminar; no se mueve el foco.

- **Área en puntos porcentuales**: `median_area_fraction`, `max_area_fraction`
  y `point.area_fraction` se multiplican por 100 antes de escribir
  (`0,048` → `4,8`). Nunca mostrar la fracción cruda en las fichas, la tabla ni
  los ejes.
- **Lote sin puntos**: si `points` está vacío, `dominant_severity` es
  `sin_datos` y `worst` también está vacío. Mostrar `#report-empty`, no la
  tabla ni los gráficos vacíos; el sello queda en «Sin datos» y
  `#report-severe` oculto.
- **Peor hoja sin datos**: si `worst` no tiene elementos,
  `#report-worst-area` y `#report-worst-name` quedan en «—» y sin `title`.

### 14.11 Guardar una copia

`#report-save` vive en `.report-actions`, antes de Imprimir y Cerrar, con estilo
fantasma y 44 px de alto. Al pulsarlo, `app.js` clona la hoja ya renderizada y
arma un HTML autocontenido:

- embebe `tokens.css` y `styles.css` completos en un `<style>`, más un bloque
  mínimo para que la hoja se centre y crezca sin scroll;
- conserva los SVG en línea, las tablas y las notas; no hay imágenes remotas que
  se rompan al abrir el archivo sin el servidor;
- quita `.report-states` y `.report-actions`, y reemplaza cualquier `<button>`
  restante por un `<span class="report-saved-name">`, para que la copia no tenga
  controles muertos;
- el `<title>` usa `#report-title` y `#report-subtitle`.

La escritura usa `window.showSaveFilePicker` con nombre sugerido
`informe-lote-AAAA-MM-DD.html`; el usuario elige carpeta y nombre. Si la API no
existe o falla, se descarga con un enlace `download`. El estado se anuncia en
`#report-save-status` (`role="status"`), oculto en impresión; cancelar el
selector no deja mensaje de error. La copia conserva `@media print` y las pilas
tipográficas estáticas, así que también se imprime bien desde el archivo. Las
tipografías remotas siguen siendo deuda: sin red se usan los fallbacks.

## 15. Vaciar el almanaque — «Limpiar»

El botón `#clear-archive` cierra la fila de herramientas de «Archivo», después
de Actualizar, con la clase `icon-button--danger`: la única acción destructiva
del panel. Nace `disabled` y se habilita solo con el almanaque no vacío y sin
operación en curso; durante el vaciado `setBusy` lo vuelve a deshabilitar.

Reutiliza `#confirm-delete` para no multiplicar diálogos. `app.js` guarda
`pendingClear` y escribe:

- título `#confirm-title`: «¿Vaciar el almanaque?»;
- texto `#confirm-text`: cantidad real de inspecciones y «No se puede deshacer»;
- aceptar `#confirm-accept`: «Vaciar archivo», con `button--danger`.

Cancelar o Escape no envía nada. Confirmar llama a `DELETE /api/inspections`,
oculta `#result`, limpia la selección y recarga el Almanaque; el estado vacío
(«La huerta espera su primera hoja.») y el botón deshabilitado son la
confirmación visual. El mismo diálogo conserva el flujo de borrado individual,
que vuelve a escribir sus propios textos antes de abrirse. No hay deshacer: la
confirmación es la última barrera (ADR-011).
