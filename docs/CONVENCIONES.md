# Convenciones

## Idioma

- Documentación, comentarios y mensajes de error: **español**.
- Identificadores de código (módulos, clases, funciones, variables): **inglés**,
  en `snake_case` para funciones y variables, `PascalCase` para clases.
- No se mezcla idioma dentro de un mismo archivo.

## Código

- Sin código comentado "por si acaso": el historial de git cumple ese rol.
- Sin atribución de autor en el código: va en el README o en el historial.
- Una sola fuente de verdad por constante (límites de subida, formatos, umbrales).
- Todo `os.environ` se lee en `app/config.py`, en ningún otro archivo.
- Funciones del core anotadas con tipos; `mypy` sin errores nuevos.
- Los errores de dominio se lanzan, no se imprimen; la traducción a HTTP vive en
  `app/errors.py`.

## Tests

- `tests/test_contract.py` no se modifica para que pase: si falla, se corrige el
  código.
- Todo módulo nuevo trae al menos un test de su rama de error, no solo del camino
  feliz.
- Los datos de test del core son sintéticos y deterministas. Las imágenes reales
  viven en `tests/golden/` y se marcan `slow` si demoran.
- Los tests nunca escriben en `imgs/` ni en `storage/` real.

## Git

- Commits narrativos: `tipo(alcance): qué y por qué`, tipos `feat`, `fix`,
  `test`, `docs`, `refactor`, `chore`.
- Un commit no mezcla cambio de contrato con cambio de implementación.
- No se commitean `storage/`, `data/`, `sandbox/` ni cachés.

## Nombres de artefactos

- Identificador de inspección: `uuid4().hex`, generado por el servidor.
- En `storage/`: `<id>-original.png`, `<id>-result.png`, `<id>.json`.
- El JSON es el commit point: se escribe último y es lo único que se lista.
- En `data/manifest.jsonl`, una línea por imagen con `path`, `sha256`, `hoja`,
  `variante_de` y `estado`.
