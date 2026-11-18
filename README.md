# El Libro de las Hojas — análisis de hojas de tabaco

Desarrollé esta aplicación para caracterizar hojas de tabaco a partir de
imágenes, usando **solo procesamiento de imágenes clásico** (OpenCV y NumPy),
sin aprendizaje profundo ni modelos preentrenados.

## Presentación académica

- **Materia:** Técnicas de Procesamiento Digital de Imágenes
- **Año y cuatrimestre de cursada:** 2026, segundo cuatrimestre
- **Nombre y apellido:** Nicolás Gold
- **Docente:** Juan Bonini

### ¿Qué me motivó a crear este proyecto?

Trabajo en el rubro del tabaco y participo en la adquisición de materia prima.
Por eso, me interesó explorar cómo el procesamiento digital de imágenes puede
ayudarme a observar y caracterizar hojas de tabaco de una forma práctica,
reproducible y fácil de interpretar. Desarrollé la aplicación para medir
lesiones, clorosis, color y textura, y para poder revisar visualmente cómo se
obtiene cada resultado. Elegí técnicas clásicas de visión por computadora para
que el método y sus decisiones sean visibles, en lugar de depender de un modelo
opaco.

### Problemáticas que encontré y cómo las resolví

- **Separar las lesiones pardas del amarillamiento (clorosis):** ambos pueden
  aparecer en una misma hoja y confundirse por el color. Implementé criterios
  distintos: detecto la lesión por sus características de color y la clorosis
  por el matiz; las informo por separado.
- **Variaciones de iluminación, fondo y tamaño de las imágenes:** podían afectar
  el recorte y las mediciones de textura. Incorporé una etapa que aísla la hoja
  por contraste con el fondo y llevo las imágenes a un tamaño de referencia para
  comparar la textura de forma más consistente.
- **Variantes y duplicados en el conjunto de datos:** contar cada archivo como
  una muestra independiente podía sesgar la evaluación. Organicé el análisis
  por hoja de origen y detecté duplicados para no tratarlos como casos
  distintos.
- **Hacer comprensibles y verificables los resultados:** no me alcanzaba con
  mostrar una medida final. Por eso, incorporé una traza visual de las etapas,
  registro de parámetros y pruebas para comprobar el comportamiento del
  procesamiento.

## Documentación

| Documento | Contenido |
|---|---|
| [`docs/DECISIONES.md`](docs/DECISIONES.md) | ADRs: core sin HTTP, visión clásica, unidad de muestreo, segmentación |
| [`docs/DESIGN.md`](docs/DESIGN.md) | Sistema visual “El Libro de las Hojas”: paleta, tipografía y componentes |
| [`docs/CONVENCIONES.md`](docs/CONVENCIONES.md) | Idioma, nombres, tests y commits |
| [`docs/VALIDACION.md`](docs/VALIDACION.md) | Resultados de validación por lote |
| [`docs/TRASPASO.md`](docs/TRASPASO.md) | Estado y próximos pasos del proyecto |

## Mapa del proyecto

| Carpeta | Qué es | ¿Se versiona? |
|---|---|---|
| `core/` | La librería: aislamiento, preproceso, calidad, compuerta de dominio, segmentación, clorosis, morfometría, descriptores y render. Solo NumPy/OpenCV, sin HTTP. | sí |
| `app/` | FastAPI: valida la subida, llama al `LeafInspector` y persiste. | sí |
| `frontend/` | Una sola página: subida, medidas, capas del proceso, almanaque e informe; incluye diez imágenes de prueba servidas por CDN. | sí |
| `tests/` | Contrato, arquitectura y unitarios. `python -m pytest` en verde. | sí |
| `docs/` | ADRs (`DECISIONES.md`), diseño visual, convenciones, veredictos y traspaso. | sí |
| `imgs/` | Dataset dado, inmutable (2000 PNG de 800×800). | no |
| `data/golden/` | Conjunto dorado de manifest y máscaras anotadas que uso para validar; son datos, no código. | no |
| `sandbox/` | Scripts de trabajo, fotos externas y almacén de demo. Ver [`sandbox/LEEME.md`](sandbox/LEEME.md). | no |
| `storage/` | Almanaque local de la API. | no |

## Dataset

El conjunto que analizo en `imgs/` contiene 210 hojas originales, 1680 variantes
aumentadas (8 por hoja) y 110 variantes con nombre duplicado. Tomo **la hoja**, no
el archivo, como unidad de muestreo. Las imágenes son recortes de superficie
foliar: analizo lesiones, color, textura y nervaduras, no el contorno de la hoja
completa. Cuando subo fotos nuevas con fondo, `LeafIsolator` recorta primero la
hoja dominante; los recortes del conjunto de datos se conservan tal cual
(`primer_plano`). Incluí diez muestras para la interfaz en `frontend/examples/`;
Vercel las sirve desde su CDN, sin empaquetar el conjunto completo ni invocar la
función Python para cada imagen. El selector descarga miniaturas WebP de 320 px
(≈98 KB en total) y conserva el PNG original para analizarlo solo cuando se elige
una muestra.

## Qué analizo

Distingo dos familias de tejido (ADR-014 y ADR-015):

- **Lesión parda**: identifico el tejido oxidado, donde el rojo alcanza al
  verde. Uso un umbral estricto para marcar las manchas y otro más bajo,
  calculado por hoja, para recuperar el halo pálido sin tocar la nervadura.
- **Clorosis**: identifico por separado el tejido que perdió el verde y quedó
  amarillo, sin oxidarse. La mido por ángulo de matiz en Lab, no por canales de
  color, porque puede solaparse con la lesión.

En cada inspección que proceso guardo una **traza visual** de 17 capas: lo que
entró, lo que corregí y las decisiones del análisis, en el mismo orden en la
pantalla y en el disco.

## Cómo correrlo

Para ejecutar la aplicación que desarrollé:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
python -m uvicorn app.main:app --reload --port 8765
python -m pytest
```

Al ejecutar la aplicación, la raíz `/` sirve la pantalla de **El Libro de las
Hojas** y los artefactos se publican bajo `/media`. El almacenamiento por defecto
es `storage/`; puedo cambiarlo con
`FELLOWSHIP_STORAGE_DIR` (también existen `FELLOWSHIP_FRONTEND_DIR`,
`FELLOWSHIP_MAX_UPLOAD_BYTES` y `FELLOWSHIP_ALLOWED_FORMATS`).

### Con base de datos

Configuré la persistencia para que el registro de análisis pueda guardarse en
Postgres en vez de en el disco (ADR-016). Sin `DATABASE_URL`, los archivos siguen
siendo el camino por defecto.

```powershell
docker compose up -d                                  # postgres 16 en 5433
python -m app.db.migrate                              # crea la tabla inspections
$env:DATABASE_URL = "postgresql://fellowship:fellowship@127.0.0.1:5433/fellowship"
python -m uvicorn app.main:app --reload --port 8765
```

- La base guarda el payload y **un solo PNG**, el original. El overlay y las 17
  capas se regeneran cuando el visor las pide, con una caché en memoria
  (`FELLOWSHIP_MEDIA_CACHE_SIZE`, 8 registros por defecto). La primera vista de
  un registro tarda ≈ 0,9 s; la segunda, milisegundos.
- `/api/health` agrega `database`: `archivos` sin DSN, `ok` si el ping responde y
  `sin conexión` si no.
- En producción se usa un DSN gestionado (Neon, Supabase) con
  `sslmode=require`; en serverless se abre una conexión por request en vez de un
  pool. `psycopg` se instala con `pip install -e ".[dev]"` y solo se importa
  cuando hay base configurada.
- En serverless con Postgres, el PNG del resultado se reutiliza desde la caché
  al mostrar la inspección y las capas se codifican recién cuando se solicitan;
  así se evita volver a ejecutar el pipeline y codificar capas que el repositorio
  SQL no persiste.
- Los tests de base se saltean solos si no hay servidor. Con la base levantada
  corren además los de Postgres —contrato, repositorio, `/media`, login e
  historial— contra `fellowship_test` (se cambia con
  `FELLOWSHIP_TEST_DATABASE_URL`).

### Acceso con login

Cuando configuro `DATABASE_URL`, el almanaque pide usuario y contraseña
(ADR-017); sin base, la demo sigue abierta. El primer administrador se crea
automáticamente:

```powershell
$env:DATABASE_URL = "postgresql://fellowship:fellowship@127.0.0.1:5433/fellowship"
$env:FELLOWSHIP_SECRET_KEY = "una-cadena-larga-y-secreta"
$env:FELLOWSHIP_ADMIN_USER = "nico"
$env:FELLOWSHIP_ADMIN_PASSWORD = "una-clave-de-8-o-mas"
python -m app.db.migrate
python -m uvicorn app.main:app --reload --port 8765
```

- `FELLOWSHIP_SECRET_KEY` firma la cookie de sesión: si cambia, todas las sesiones
  se cierran. Vacía, se genera una por proceso y las sesiones no sobreviven al
  reinicio. `FELLOWSHIP_SESSION_HOURS` (12 por defecto) fija su duración.
- El administrador se crea **solo si la tabla `users` está vacía**. Después, las
  cuentas se manejan desde el botón **Usuarios** del encabezado (solo lo ve el
  `admin`): alta con clave y rol, y baja por fila. `POST /api/auth/users` y
  `DELETE /api/auth/users/{id}` hacen lo mismo sin pantalla.
- Las contraseñas se guardan con `scrypt` y sal por usuario; nunca se escriben en
  claro ni se devuelven por la API.
- **Cada uno ve sus hojas** (ADR-018): el `operador` solo ve, abre, descarga,
  informa y vacía lo suyo; el `admin` ve el almanaque completo. Dar de baja una
  cuenta deja sus hojas en el almanaque sin dueño, y el `admin` las purga con
  **Borrar hojas sin dueño** (o `DELETE /api/inspections?unassigned=true`).
- Cada hoja registra quién la subió y con qué versión del software. El filtro del
  almanaque y el sello `v0.2.0` salen de ahí, y `GET /api/versions` resume cuántas
  hojas midió cada versión.

### Revisar y anotar el detector

```powershell
python sandbox\auditar.py 80      # histéresis, clorosis y costo por hoja -> sandbox/auditoria.txt
python sandbox\anotar.py          # corregir las máscaras de calibración con el mouse
python sandbox\golden.py score    # IoU, Dice, precisión y recall contra las máscaras
```

`anotar.py` levanta un corrector en `http://127.0.0.1:8140`: abre cada hoja con su
máscara candidata encima, se pinta lo que falta y se borra lo que sobra. Al
guardar, la máscara queda marcada como humana en `_provenance.json`, y desde ahí
el puntaje del conjunto dorado mide acierto en vez de movimiento del detector.

### API

| Método | Ruta | Respuesta |
|---|---|---|
| `GET` | `/api/health` | estado y versión |
| `GET` | `/api/config` | límite de subida, formatos y si hace falta sesión |
| `POST` | `/api/auth/login` | `200` con el usuario y la cookie de sesión |
| `POST` | `/api/auth/logout` | `204`; borra la cookie |
| `GET` | `/api/auth/me` | quién está en sesión (o `null`) y si hay login |
| `POST` | `/api/auth/password` | `204`; cambia la contraseña propia |
| `GET` | `/api/auth/users` | usuarios registrados (solo `admin`) |
| `POST` | `/api/auth/users` | `201`; alta de usuario (solo `admin`) |
| `DELETE` | `/api/auth/users/{id}` | `204`; da de baja la cuenta (solo `admin`, nunca la propia) |
| `POST` | `/api/inspections` | `201` con la inspección completa |
| `GET` | `/api/inspections` | historial, más reciente primero (el `operador` solo ve el suyo) |
| `GET` | `/api/inspections/{id}` | una inspección; la de otro responde `404` |
| `GET` | `/api/versions` | versiones registradas y cuántas hojas midió cada una |
| `GET` | `/api/reports/lot` | informe agregado del lote (el `operador` agrega solo sus hojas) |
| `DELETE` | `/api/inspections` | `204`; vacía el archivo: todo (admin) o lo propio (operador) |
| `DELETE` | `/api/inspections/{id}` | `204`; la de otro responde `404` |

`GET /api/inspections` acepta `limit`, `offset` y los filtros del historial:
`version`, `owner`, `since`, `until`, `q` (nombre de archivo) y
`unassigned=true` (hojas sin cuenta detrás; solo `admin`). El `owner` que manda
un operador se ignora: ve lo suyo y nada más (ADR-018).

Los errores de dominio viajan como `{"detail": {"code": "...", "message": "..."}}`
con los códigos `INVALID_FILE`, `FILE_TOO_LARGE`, `IMAGE_UNUSABLE`,
`IMAGE_NOT_A_LEAF`, `INSPECTION_NOT_FOUND` y, con base, `NO_AUTENTICADO` (`401`),
`CREDENCIALES_INVALIDAS` (`401`), `SIN_PERMISO` (`403`), `USUARIO_EXISTENTE`
(`409`) y `USUARIO_NO_ENCONTRADO` (`404`). Una imagen que no parece hoja se
rechaza con `422` y el motivo medido (ver ADR-008).

El botón **Informe** del Almanaque pide `GET /api/reports/lot` y muestra cifras,
histograma, dispersión, ranking y una tabla imprimible del lote aceptado. Los
cortes de severidad (1 %, 5 %, 15 %) son operativos, no agronómicos (ADR-010).

**Guardar** descarga el informe como una página HTML autocontenida (tokens,
estilos, tablas y SVG incluidos) en la carpeta que elija el usuario mediante el
selector nativo del navegador; si no está disponible, cae a la descarga normal.
**Limpiar** vacía el archivo con una única `DELETE /api/inspections`, previa
confirmación con la cantidad de inspecciones (ADR-011). Para un operador vacía
solo lo suyo; para el administrador, el almanaque completo. Con un filtro puesto
queda deshabilitado: borraría más de lo que se ve en pantalla.

## Despliegue

Publiqué una demo en [el-libro-de-las-hojas.vercel.app](https://el-libro-de-las-hojas.vercel.app)
y el código fuente en [GitHub](https://github.com/nagold86/el-libro-de-las-hojas).

Configuré la pantalla y la API para correr como una sola función Python
(`app/main.py`, 60 s de duración máxima según `vercel.json`), así que no hay CORS
ni segundo servicio. Estas son condiciones de la demo, no de producción (ADR-012):

- **Almacenamiento efímero.** Con `VERCEL` presente, `app/config.py` mueve el
  repositorio a `/tmp/fellowship-storage` y baja el límite de subida a 4 MB
  (Vercel corta el cuerpo en 4,5 MB). En local no cambia nada: `storage/` y
  10 MB. `FELLOWSHIP_STORAGE_DIR` sigue disponible para apuntar a un volumen
  persistente.
- **El almanaque es de sesión** mientras no haya `DATABASE_URL`. Las fotos y
  medidas sobreviven lo que viva la instancia y pueden perderse al reiniciarse.
  Con base configurada el historial y los usuarios persisten (ADR-016 y ADR-017),
  y la demo deja de estar abierta: pide usuario y contraseña.
- **Solo publico lo necesario.** La configuración de Vercel excluye el conjunto
  de imágenes, los archivos locales, las pruebas y los recursos de desarrollo.

El repo está conectado al proyecto: cada push a `main` publica solo. Para
publicar sin commit, desde la raíz:

```powershell
git push origin main     # deployment de producción, ~30 s
vercel --prod            # publicar el working copy sin commit
```

Con base configurada, un deployment contra una base nueva necesita el esquema:
`python -m app.db.migrate` con `DATABASE_URL` apuntando a esa base. Sin él, el
login responde `500` (`relation "users" does not exist`).

## Estado actual

Implementé y validé el pipeline clásico con la suite de pruebas (282 pruebas en
verde; las de Postgres se omiten si no hay servidor):

- `core/` implementado de punta a punta (aislamiento, preproceso de dos vistas,
  calidad, compuerta de dominio, segmentación con histéresis, clorosis,
  morfometría, descriptores y render) sin dependencias HTTP.
- `app/` con contrato Pydantic, errores mapeados, persistencia atómica o en
  Postgres detrás de una misma interfaz (ADR-016), login con sesión firmada sobre
  la tabla `users`, registro de versiones publicadas (ADR-017) y el informe del
  lote calculado al leer.
- `frontend/` de una sola página con el sistema visual de El Libro de las Hojas,
  las 17 capas del proceso, el informe del lote (cifras, gráficos, impresión A4 y
  copia HTML guardable), la puerta de entrada, el historial con filtros por
  versión / quién / nombre y el vaciado confirmado del almanaque.
- `tests/` de contrato, arquitectura y unitarios; `python -m pytest` en verde.
- Publicado en Vercel como demo (`/tmp`, 4 MB): subida, informe, artefactos y
  vaciado verificados contra la URL pública, sin errores de consola (ADR-012).

Como próximos pasos, me queda corregir a mano las máscaras del conjunto dorado y
decidir si debo restar la clorosis del área que reporto como lesión. Detallo el
estado en [`docs/TRASPASO.md`](docs/TRASPASO.md).
