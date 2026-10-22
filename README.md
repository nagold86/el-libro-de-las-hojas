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

## Estructura

```
imgs/        dataset dado, inmutable (2000 PNG 800x800)
core/        librería pura: preproceso, segmentación, medidas, descriptores
app/         FastAPI: valida, delega en el core y persiste
tests/       contrato, arquitectura, unitarios y conjunto golden
frontend/    consumidor del contrato
docs/        decisiones, convenciones y validación
data/        manifest y duplicados derivados de la ingesta
storage/     artefactos de la API
fellowship/  la Comunidad de agentes
```

## Dataset

`imgs/` contiene 210 hojas originales, 1680 variantes aumentadas (8 por hoja) y
110 variantes con nombre duplicado. La unidad de muestreo es **la hoja**, no el
archivo. Las imágenes son recortes de superficie foliar: se analizan lesiones,
color, textura y nervaduras, no el contorno de la hoja completa. Las fotos
nuevas con fondo pasan primero por `LeafIsolator`, que recorta la hoja dominante;
los recortes del dataset se conservan tal cual (`primer_plano`).

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

### API

| Método | Ruta | Respuesta |
|---|---|---|
| `GET` | `/api/health` | estado y versión |
| `GET` | `/api/config` | límite de subida y formatos aceptados |
| `POST` | `/api/inspections` | `201` con la inspección completa |
| `GET` | `/api/inspections` | listado, más reciente primero |
| `GET` | `/api/inspections/{id}` | una inspección |
| `GET` | `/api/reports/lot` | informe agregado del lote aceptado |
| `DELETE` | `/api/inspections` | `204`; vacía el almanaque completo |
| `DELETE` | `/api/inspections/{id}` | `204` |

Los errores de dominio viajan como `{"detail": {"code": "...", "message": "..."}}`
con los códigos `INVALID_FILE`, `FILE_TOO_LARGE`, `IMAGE_UNUSABLE`,
`IMAGE_NOT_A_LEAF` e `INSPECTION_NOT_FOUND`. Una imagen que no parece hoja se
rechaza con `422` y el motivo medido (ver ADR-008).

El botón **Informe** del Almanaque pide `GET /api/reports/lot` y muestra cifras,
histograma, dispersión, ranking y una tabla imprimible del lote aceptado. Los
cortes de severidad (1 %, 5 %, 15 %) son operativos, no agronómicos (ADR-010).

**Guardar** descarga el informe como una página HTML autocontenida (tokens,
estilos, tablas y SVG incluidos) en la carpeta que elija el usuario mediante el
selector nativo del navegador; si no está disponible, cae a la descarga normal.
**Limpiar** vacía el almanaque con una única `DELETE /api/inspections`, previa
confirmación con la cantidad de inspecciones (ADR-011).

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
- **El almanaque es de sesión.** Las fotos y medidas sobreviven mientras la
  instancia siga viva y pueden perderse al reiniciarse. La demo muestra el
  método y el contrato, no un historial garantizado.
- **Solo viaja lo necesario.** `.vercelignore` deja fuera `imgs/`, `storage/`,
  `docs/`, `fellowship/`, `tests/` y `sandbox/`.

Para republicar, desde la raíz:

```powershell
vercel --prod
```

## Estado

Esqueleto contract-first completo y verificado con la suite de tests:

- `core/` implementado de punta a punta (aislamiento, preproceso, calidad,
  compuerta de dominio, segmentación, morfometría, descriptores y overlay) sin
  dependencias HTTP.
- `app/` con contrato Pydantic, errores mapeados, persistencia atómica y el
  informe del lote calculado al leer.
- `frontend/` de una sola página con el sistema visual de El Libro de las Hojas,
  el informe del lote (cifras, gráficos, impresión A4 y copia HTML guardable) y
  el vaciado confirmado del almanaque.
- `tests/` de contrato, arquitectura y unitarios; `python -m pytest` en verde.
- Publicado en Vercel como demo (`/tmp`, 4 MB): subida, informe, artefactos y
  vaciado verificados contra la URL pública, sin errores de consola (ADR-012).

