# Fellowship — análisis de hojas de tabaco

Caracterización de hojas de tabaco a partir de imágenes, usando **solo
procesamiento de imágenes clásico** (OpenCV, NumPy, SciPy, pandas). Sin
aprendizaje profundo, sin modelos preentrenados.

La identidad visual sigue un sistema propio de inspiración tolkieniana
(pergamino, tinta y oro), definido en [`docs/DESIGN.md`](docs/DESIGN.md) y
propiedad del agente de diseño.

## Documentación

| Documento | Contenido |
|---|---|
| [`fellowship/PIPELINE.md`](fellowship/PIPELINE.md) | Contrato de arquitectura, dueño de cada archivo y dataset real |
| [`fellowship/README.md`](fellowship/README.md) | El equipo de diez agentes y sus reglas |
| [`fellowship/roster.yaml`](fellowship/roster.yaml) | Registro legible por máquina del equipo |
| [`docs/DECISIONES.md`](docs/DECISIONES.md) | ADRs: core sin HTTP, visión clásica, unidad de muestreo, segmentación |
| [`docs/DESIGN.md`](docs/DESIGN.md) | Sistema visual “El Libro de las Hojas”: paleta, tipografía y componentes |
| [`docs/CONVENCIONES.md`](docs/CONVENCIONES.md) | Idioma, nombres, tests y commits |
| [`docs/VALIDACION.md`](docs/VALIDACION.md) | Veredictos de Boromir por lote |
| [`docs/TRASPASO.md`](docs/TRASPASO.md) | Estado al cierre de la sesión: qué hay, dónde y qué sigue |

## Mapa del proyecto

| Carpeta | Qué es | ¿Se versiona? |
|---|---|---|
| `core/` | La librería: aislamiento, preproceso, calidad, compuerta de dominio, segmentación, clorosis, morfometría, descriptores y render. Solo NumPy/OpenCV, sin HTTP. | sí |
| `app/` | FastAPI: valida la subida, llama al `LeafInspector` y persiste. No hace visión. | sí |
| `frontend/` | Una sola página: subida, medidas, capas del proceso, almanaque e informe. | sí |
| `tests/` | Contrato, arquitectura y unitarios. `python -m pytest` en verde. | sí |
| `docs/` | ADRs (`DECISIONES.md`), diseño visual, convenciones, veredictos y traspaso. | sí |
| `fellowship/` | El equipo de agentes y el contrato de arquitectura. | sí |
| `imgs/` | Dataset dado, inmutable (2000 PNG de 800×800). | no |
| `data/golden/` | Conjunto dorado: manifest y máscaras anotadas. Vive solo en el equipo de trabajo: son datos, no código. | no |
| `sandbox/` | Scripts de trabajo, fotos externas y almacén de demo. Ver [`sandbox/LEEME.md`](sandbox/LEEME.md). | no |
| `storage/` | Almanaque local de la API. | no |

## Dataset

`imgs/` contiene 210 hojas originales, 1680 variantes aumentadas (8 por hoja) y
110 variantes con nombre duplicado. La unidad de muestreo es **la hoja**, no el
archivo. Las imágenes son recortes de superficie foliar: se analizan lesiones,
color, textura y nervaduras, no el contorno de la hoja completa. Las fotos
nuevas con fondo pasan primero por `LeafIsolator`, que recorta la hoja dominante;
los recortes del dataset se conservan tal cual (`primer_plano`).

## Qué mide

Dos familias de tejido, separadas a propósito (ADR-014 y ADR-015):

- **Lesión parda**: tejido oxidado, donde el rojo alcanza al verde. El umbral
  estricto siembra las manchas y un umbral bajo, calculado por hoja, recupera el
  halo pálido que las rodea sin tocar la nervadura.
- **Clorosis**: tejido que perdió el verde y quedó amarillo, sin oxidarse. Se
  mide por ángulo de matiz en Lab, no por canales de color, y se reporta aparte
  porque puede solaparse con la lesión.

Cada inspección deja una **traza visual** de 17 capas: lo que entró, lo que se
corrigió y lo que se decidió, con el mismo orden en la pantalla y en el disco.

## Cómo correrlo

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
python -m uvicorn app.main:app --reload --port 8765
python -m pytest
```

La raíz `/` sirve la pantalla de **El Libro de las Hojas** y los artefactos se
publican bajo `/media`. El storage por defecto es `storage/`; se cambia con
`FELLOWSHIP_STORAGE_DIR` (también existen `FELLOWSHIP_FRONTEND_DIR`,
`FELLOWSHIP_MAX_UPLOAD_BYTES` y `FELLOWSHIP_ALLOWED_FORMATS`).

### Con base de datos

El registro de análisis puede vivir en Postgres en vez de en el disco (ADR-016).
Sin `DATABASE_URL` nada cambia: los archivos siguen siendo el camino por defecto.

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
- Los tests de base se saltean solos si no hay servidor. Con la base levantada
  corren además los de Postgres —contrato, repositorio, `/media`, login e
  historial— contra `fellowship_test` (se cambia con
  `FELLOWSHIP_TEST_DATABASE_URL`).

### Con login

Con `DATABASE_URL` configurada, el almanaque pide usuario y contraseña (ADR-017);
sin base la demo sigue abierta, sin puerta. El primer administrador se crea solo:

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

Demo pública: [el-libro-de-las-hojas.vercel.app](https://el-libro-de-las-hojas.vercel.app).
Repositorio: [nagold86/el-libro-de-las-hojas](https://github.com/nagold86/el-libro-de-las-hojas).

La pantalla y la API corren como una sola función Python (`app/main.py`, 60 s de
duración máxima según `vercel.json`), así que no hay CORS ni segundo servicio.
Son condiciones de demo, no de producción (ADR-012):

- **Almacenamiento efímero.** Con `VERCEL` presente, `app/config.py` mueve el
  repositorio a `/tmp/fellowship-storage` y baja el límite de subida a 4 MB
  (Vercel corta el cuerpo en 4,5 MB). En local no cambia nada: `storage/` y
  10 MB. `FELLOWSHIP_STORAGE_DIR` sigue disponible para apuntar a un volumen
  persistente.
- **El almanaque es de sesión** mientras no haya `DATABASE_URL`. Las fotos y
  medidas sobreviven lo que viva la instancia y pueden perderse al reiniciarse.
  Con base configurada el historial y los usuarios persisten (ADR-016 y ADR-017),
  y la demo deja de estar abierta: pide usuario y contraseña.
- **Solo viaja lo necesario.** `.vercelignore` deja fuera `imgs/`, `storage/`,
  `docs/`, `fellowship/`, `tests/` y `sandbox/`.

El repo está conectado al proyecto: cada push a `main` publica solo. Para
publicar sin commit, desde la raíz:

```powershell
git push origin main     # deployment de producción, ~30 s
vercel --prod            # publicar el working copy sin commit
```

Con base configurada, un deployment contra una base nueva necesita el esquema:
`python -m app.db.migrate` con `DATABASE_URL` apuntando a esa base. Sin él, el
login responde `500` (`relation "users" does not exist`).

## Estado

Pipeline clásico completo, medido y verificado con la suite de tests (282
pruebas en verde; los de Postgres se saltean solos si no hay servidor):

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

Lo que falta está en [`docs/TRASPASO.md`](docs/TRASPASO.md): corregir a mano las
máscaras del conjunto dorado, y decidir si la clorosis debe restarse del área
reportada como lesión.

