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

## 2026-10-29 — producción con base gestionada y conserjería (ADR-018 en Vercel)

- n: la demo publicada sobre el Neon del proyecto (`neon-cyclamen-school`), con
  la suite local en 282. El despliegue sale del push a `main`, porque el repo
  **sí** está vinculado a Vercel (~30 s).
- Servicio: `/api/health` → `ok`, `database: ok`, `0.2.0`; `/api/config` →
  `auth_required: true`, 4 MB; `/api/inspections` sin sesión → `401
  NO_AUTENTICADO`.
- Esquema: se aplicó desde el **SQL Editor de Neon**. La pestaña *Query* de
  Vercel abre una transacción de solo lectura (`cannot execute CREATE TABLE in a
  read-only transaction`) y el protocolo extendido rechaza varios comandos por
  pedido, así que el esquema viajó como un único bloque `DO … EXECUTE`
  (`sandbox/esquema_produccion.sql`, probado antes contra Postgres local con
  rollback). `schema_migrations` quedó con `001_init` y
  `002_users_and_versions`.
- Fallo encontrado y corregido: antes de migrar, el login respondía `500` con
  `psycopg.errors.UndefinedTable: relation "users" does not exist`, mientras
  `/api/health` decía `ok` porque solo hace `SELECT 1`. Queda como pendiente
  traducir ese caso a `503` (cambia contrato, necesita ADR).
- Credenciales: `FELLOWSHIP_SECRET_KEY`, `FELLOWSHIP_ADMIN_USER` y
  `FELLOWSHIP_ADMIN_PASSWORD` se cargaron en Production y Preview; el
  administrador lo creó `bootstrap_admin` en el arranque siguiente. Sin la clave
  de firma, `SessionSigner` genera una por proceso y las sesiones se caen entre
  instancias.
- Recorrido en navegador: login del `admin`, alta de un operador desde
  **Usuarios** y aislamiento entre las dos cuentas (el operador solo ve su hoja).
  Cierra el pendiente «no probado en navegador» del ADR-017/018.
- Sin verificar todavía: la purga de huérfanas en producción con datos reales
  (el recorrido local del mismo día la cubre: `sandbox/verificar_scope.py`,
  37/37) y los filtros por fecha.
- Veredicto: **APTO** para la demo con sesión.

---

## 2026-10-29 — alcance por dueño y conserjería (ADR-018)

- n: 11 casos HTTP nuevos en `tests/test_scope.py` (dos cuentas reales sobre
  `fellowship_test`: un `admin` y un `operador` creado en el momento) más 10 casos
  de store y repositorio. Suite completa: `python -m pytest` → **282 pasan, 0
  salteados** (44,2 s). Los 261 anteriores siguen verdes: el alcance no cambió
  ninguna medición.
- Aislamiento: el `operador` ve solo sus hojas aunque mande `owner` ajeno (el
  parámetro se ignora), pide una hoja de otro y recibe **404
  `INSPECTION_NOT_FOUND`** —el mismo de un id inexistente—, y lo mismo pasa con
  el PNG en `/media`. El `admin` abre las dos. El informe del lote suma 1 hoja
  para el operador y 2 para el administrador, y `DELETE /api/inspections` deja
  solo la hoja del compañero.
- Baja de usuario: `DELETE /api/auth/users/{id}` → **204**; la lista del `admin`
  vuelve con una sola cuenta, el login del dado de baja responde **401
  `CREDENCIALES_INVALIDAS`** y sus hojas aparecen en
  `GET /api/inspections?unassigned=true`. La purga de huérfanas las borra sin
  tocar la hoja del `admin`. La cuenta propia no se puede dar de baja (**403
  `SIN_PERMISO`**) y un id desconocido responde **404
  `USUARIO_NO_ENCONTRADO`**. Un `operador` recibe 403 en listar, crear y borrar
  usuarios, y `unassigned=true` le devuelve la lista vacía.
- Divergencia documentada: «sin dueño» no significa lo mismo en las dos
  persistencias. En archivos solo es huérfana la hoja que nunca tuvo `owner` en el
  payload; en Postgres también la que quedó con `user_id` en NULL por una baja
  (`ON DELETE SET NULL`). El contrato compartido
  (`tests/test_store_contract.py`) prueba el caso común y cada repositorio cubre
  su matiz, para que el comportamiento quede escrito y no como sorpresa.
- Repetibilidad: el detector no se tocó en este lote (huella `7fb35e2d`); el
  alcance filtra filas, no medidas, así que una hoja sigue midiendo lo mismo para
  su dueño y para el administrador.
- Fuga de datos: ninguna; ADR-018 no agrega rasgos ni umbrales, solo recorta qué
  filas ve cada cuenta. El `404` en lo ajeno es deliberado: un `403` confirmaría
  que la hoja existe.
- Recorrido en vivo: `sandbox/verificar_scope.py` contra `uvicorn` en el puerto
  8765 y la base `fellowship` → **37 de 37** comprobaciones en verde, con un
  operador `probe_scope` de usar y tirar. Al final la base quedó como estaba:
  una cuenta (`nico`) y dos hojas.
- Sin verificar todavía: el recorrido visual de la conserjería (botón
  **Usuarios**, alta, baja, «Borrar hojas sin dueño» y la opción «sin dueño» del
  filtro). El JS pasa `node --check` y todos los `id` que usa `getElementById`
  existen en `index.html`, pero el diálogo no se abrió en un navegador real.
- Veredicto: **APTO**; queda como pendiente el recorrido en navegador, ya
  declarado en [`TRASPASO.md`](TRASPASO.md).

---

## 2026-10-29 — login, historial y versiones en Postgres (ADR-017)

- n: 1 hoja del dataset (`A_IMG_20231014_162623_10`) para el recorrido de punta a
  punta; suite completa con Postgres levantado. `python -m pytest` → **261 pasan,
  0 salteados** (36,6 s), sobre `fellowship_test`. El recorrido es
  `sandbox/verificar_auth.py` contra `uvicorn` en el puerto 8767: 20 de 20
  comprobaciones en verde.
- Credenciales: la verificación corrió contra la base de prueba, con un
  administrador `nico` de usar y tirar. En la base `fellowship` solo se aplicó el
  esquema (ya estaba al día): no se creó ningún usuario ni se escribió ninguna
  hoja, así que no queda una clave inventada. `FELLOWSHIP_ADMIN_USER` y
  `FELLOWSHIP_ADMIN_PASSWORD` las define quien levante el servidor.
- Migraciones: se borraron las cuatro tablas y `python -m app.db.migrate` aplicó
  `001_init` y `002_users_and_versions`; **un proceso distinto** lista después
  `inspections`, `schema_migrations`, `software_versions` y `users`. Confirma el
  arreglo del guardado implícito (el DDL ya sobrevive al cierre de la conexión) y
  deja cerrado el pendiente de verificación real del 2026-10-28.
- Persistencia entre procesos: una hoja subida por el servidor viejo
  (`af22e69f`, dueña `nico`, `app_version` 0.2.0, huella de método `7fb35e2d`)
  reaparece en el servidor reiniciado como única hoja del almanaque, con el
  original servido desde la base (**593.837 B**). El overlay regenerado en frío
  llega por `/media` con **601.699 B**. Vaciar el almanaque después lo deja en 0.
- Puerta: sin sesión, `/api/inspections` y `/media/...` responden **401**
  (`NO_AUTENTICADO`), `/api/health` sigue abierto; clave equivocada → **401**
  `CREDENCIALES_INVALIDAS`; alta de usuario repetida → **409**
  `USUARIO_EXISTENTE`; `logout` → **204** y el historial vuelve a 401. Cookie
  manipulada y operador pidiendo alta de usuarios quedan cubiertos en
  `tests/test_auth.py`.
- Historial: filtros por nombre (`q`), dueño y versión devuelven 1 hoja cada uno;
  una versión sin hojas devuelve la lista vacía y `GET /api/versions` resume
  `0.2.0` con 1 hoja. El mismo contrato se prueba contra archivos y contra
  Postgres (`tests/test_store_contract.py`, 42 casos).
- Fallos encontrados y corregidos en el camino: la cookie salía `Secure` en
  cualquier entorno y por `http` el cliente la descartaba (11 tests de `/media`
  daban 401); el `INSERT` rompía con `ForeignKeyViolation` si el dueño ya no
  existía (ahora `user_id` se resuelve con una subconsulta y queda `NULL`); el
  guardián de columnas del `.sql` no reconocía `ADD COLUMN IF NOT EXISTS`; y un
  test de guardas apuntaba a `/api/reports` en vez de `/api/reports/lot`.
- Repetibilidad: `LeafInspector().inspect()` sobre el original guardado produce
  la capa **idéntica byte a byte** a la servida desde la base (`tests/test_media.py`);
  el detector no cambió de versión en este lote (`7fb35e2d`).
- Fuga de datos: ninguna; ADR-017 solo agrega metadatos (dueño y versión), ningún
  rasgo ni umbral nuevo sobre las hojas.
- Sin verificar todavía: el recorrido visual en navegador de la puerta, los
  filtros y el sello de versión. El JS pasó `node --check` y la API está verificada
  de punta a punta, así que el riesgo está en la maqueta, no en los datos.
- Veredicto: **APTO**; el pendiente del 2026-10-28 sobre el camino de base queda
  cerrado.

---

## 2026-10-28 — registro en Postgres y capas regeneradas (ADR-016)

- n: 1 hoja del dataset (`A_IMG_20231014_162623_10`) para el costo de
  regeneración; suite completa (184 pasan, 36 salteados) para lo demás.
  `sandbox/medir_regeneracion.py` y `python -m pytest`.
- Qué se guarda: el original (**580 KB**) y el payload; el overlay y las 17 capas
  (**4,3 MB**) no se guardan. El registro completo habría sido ≈ 4,8 MB.
- Costo de regenerar: **0,90 s** en frío (0,988 / 0,901 / 0,900 en tres corridas)
  para las 18 imágenes, y **0,004 ms** la segunda vista desde la caché. En modo
  archivos no se regenera: `/media` sigue siendo `StaticFiles` sobre el disco.
- Repetibilidad: la capa servida es **idéntica byte a byte** a la que produce
  `LeafInspector().inspect()` sobre el original guardado (`tests/test_media.py`),
  que es lo que hace aceptable no guardar los PNG.
- Contrato: mismas URLs y mismos campos que antes. Agregados: `method_versions`
  en el informe del lote y `database` en `/api/health`.
- Cableado verificado sin servidor (`sandbox/verificar_cableado.py`):
  `/api/health` responde `archivos` sin DSN (0,12 s) y `sin conexión` con un DSN
  caído (2,1 s, el tope del ping de salud); `python -m app.db.migrate` sale con 2
  y un mensaje si falta `DATABASE_URL`, y con 1 y el error del driver si el
  servidor no responde, nunca con un traceback.
- Fuga de datos: ninguna; no hay ninguna métrica nueva del pipeline.
- Modo archivos de punta a punta contra la app real (`uvicorn`, puerto 8765):
  subida de una hoja nueva → 17 capas publicadas, overlay (607 KB) y capa
  (3,8 KB) servidos desde el disco, y el informe marca la huella `46838de8` para
  la nueva contra `sin_huella` en los 4 registros viejos. Borrar ese registro
  devolvió el almanaque a 4.
- **Pendiente de verificación real.** Esta máquina no tiene Docker, ni Postgres,
  ni WSL operativo, así que el camino de base **no se ejecutó**: los 36 tests de
  Postgres se saltean con el mensaje de cómo levantar la base. Sin servidor se
  cuidan el esquema y el `INSERT` (columnas del `.sql`, placeholders y aridad de
  `_columns`). Falta, en una máquina con Docker: `docker compose up -d`,
  `python -m app.db.migrate`, correr la suite sin *skip* y hacer la prueba de
  persistencia tras reiniciar el proceso (criterio 3 del plan).
- Veredicto: **APTO en modo archivos** (no cambia comportamiento); **PENDIENTE**
  en modo base hasta poder levantarla.

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
