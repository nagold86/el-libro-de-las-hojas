"""Umbrales que el operario puede mover, con su rango y su explicación.

Gandalf gobierna este módulo: decide qué es ajustable y qué no. Un parámetro
entra acá solo si (a) su significado se puede explicar en una frase, (b) tiene
un rango en el que el método sigue siendo el mismo y (c) su cambio queda
registrado en la huella del método (``method_fingerprint``), para que el informe
del lote no promedie dos criterios distintos sin avisar.

Este archivo es la única fuente de verdad de los valores por defecto: los
espeja en ``PipelineSettings`` y un test verifica que no se separen.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, fields, replace
from typing import Any

from core.exceptions import InvalidTuning
from core.pipeline import PipelineSettings


@dataclass(frozen=True)
class ParameterSpec:
    """Ficha de un umbral: qué mueve, entre qué valores y con qué defecto."""

    key: str
    label: str
    help: str
    group: str
    minimum: float
    maximum: float
    step: float
    default: float
    unit: str = ""
    integer: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "label": self.label,
            "help": self.help,
            "group": self.group,
            "min": self.minimum,
            "max": self.maximum,
            "step": self.step,
            "default": self.default,
            "unit": self.unit,
            "integer": self.integer,
        }


# Orden de la pantalla: primero lo que más mueve el resultado.
PARAMETERS: tuple[ParameterSpec, ...] = (
    ParameterSpec(
        key="redness_threshold",
        label="Pardeamiento (rojo sobre verde)",
        help=(
            "Puntaje (R−G)/(R+G). Bajarlo marca más tejido como mancha; subirlo "
            "solo deja pasar las manchas muy oxidadas."
        ),
        group="core_lesiones",
        minimum=0.0,
        maximum=0.40,
        step=0.01,
        default=0.0,
        unit="puntaje",
    ),
    ParameterSpec(
        key="darkness_threshold",
        label="Oscurecimiento de la mancha",
        help=(
            "Cuánto más oscuro que su entorno debe ser un píxel para contar como "
            "mancha oscura. 0 apaga este criterio y deja solo el pardeamiento."
        ),
        group="core_lesiones",
        minimum=0.0,
        maximum=0.90,
        step=0.05,
        default=0.35,
        unit="fracción",
    ),
    ParameterSpec(
        key="min_lesion_area_fraction",
        label="Área mínima de una mancha",
        help=(
            "Fracción de la superficie de la hoja que debe ocupar un componente "
            "para no ser descartado como ruido."
        ),
        group="manchas",
        minimum=0.00001,
        maximum=0.02,
        step=0.00001,
        default=0.0002,
        unit="de la hoja",
    ),
    ParameterSpec(
        key="hysteresis_max_growth_px",
        label="Halo que se recupera",
        help=(
            "Cuántos píxeles puede crecer una mancha desde su núcleo para "
            "recuperar el borde pálido. 0 deja solo el núcleo."
        ),
        group="core_lesiones",
        minimum=0.0,
        maximum=32.0,
        step=1.0,
        default=8.0,
        unit="px",
        integer=True,
    ),
    ParameterSpec(
        key="vein_percentile",
        label="Sensibilidad de nervaduras",
        help=(
            "Percentil de la respuesta de crestas que se marca como nervadura. "
            "Más bajo marca más red, incluidos tallos y bordes."
        ),
        group="nervaduras",
        minimum=85.0,
        maximum=99.5,
        step=0.5,
        default=97.0,
        unit="percentil",
    ),
    ParameterSpec(
        key="vein_kernel",
        label="Grosor de nervadura",
        help=(
            "Tamaño del elemento estructurante que define qué es una cresta. "
            "Nervaduras anchas piden un valor mayor."
        ),
        group="nervaduras",
        minimum=3.0,
        maximum=31.0,
        step=2.0,
        default=9.0,
        unit="px",
        integer=True,
    ),
    ParameterSpec(
        key="chlorosis_hue_threshold",
        label="Amarillamiento (clorosis)",
        help=(
            "Ángulo de matiz b*/(|a*|+b*): 0,63 es verde sano y 1 es amarillo "
            "puro. Bajarlo marca más tejido pálido como clorosis."
        ),
        group="core_clorosis",
        minimum=0.70,
        maximum=0.99,
        step=0.01,
        default=0.85,
        unit="ángulo",
    ),
    ParameterSpec(
        key="core2_redness_threshold",
        label="Pardeamiento por cromaticidad",
        help=(
            "Umbral (R−G)/(R+G) usado por Core2. Bajarlo incluye cambios de color "
            "más sutiles; subirlo exige más señal parda."
        ),
        group="core2_lesiones",
        minimum=-0.10,
        maximum=0.40,
        step=0.01,
        default=0.02,
        unit="puntaje",
    ),
    ParameterSpec(
        key="core2_darkness_threshold",
        label="Oscuridad residual",
        help=(
            "Caída de luminancia tras normalizar la iluminación. Solo se suma a "
            "lesión cuando también hay cambio cromático."
        ),
        group="core2_lesiones",
        minimum=0.0,
        maximum=0.80,
        step=0.02,
        default=0.22,
        unit="fracción",
    ),
    ParameterSpec(
        key="core2_chlorosis_yellow_threshold",
        label="Cromaticidad amarilla",
        help=(
            "Peso de rojo y verde frente al azul. Bajarlo amplía el tejido candidato "
            "a clorosis; el balance verde-rojo lo separa del tejido sano."
        ),
        group="core2_clorosis",
        minimum=0.0,
        maximum=0.45,
        step=0.01,
        default=0.10,
        unit="cromaticidad",
    ),
    ParameterSpec(
        key="core2_chlorosis_green_balance_max",
        label="Límite verde-rojo de clorosis",
        help=(
            "Máximo g−r admitido como amarillo. Subirlo tolera más verde; bajarlo "
            "hace la clorosis más selectiva."
        ),
        group="core2_clorosis",
        minimum=0.0,
        maximum=0.30,
        step=0.01,
        default=0.06,
        unit="balance",
    ),
    ParameterSpec(
        key="isolation_sensitivity",
        label="Sensibilidad del recorte",
        help=(
            "Cuánta diferencia de color con el fondo hace falta para considerar "
            "un píxel hoja. Más alto recorta más ajustado; más bajo deja pasar "
            "sombra o mesa."
        ),
        group="aislamiento",
        minimum=0.4,
        maximum=3.0,
        step=0.1,
        default=1.0,
        unit="×",
    ),
    ParameterSpec(
        key="min_sharpness",
        label="Nitidez mínima",
        help=(
            "Varianza del laplaciano por debajo de la cual la imagen se rechaza "
            "por borrosa. 0 acepta cualquier nitidez."
        ),
        group="calidad",
        minimum=0.0,
        maximum=100.0,
        step=1.0,
        default=15.0,
        unit="varianza",
    ),
    # --- Compuerta: solo decide si la imagen entra, no cuánto se mide ----------
    # Va última porque se toca cuando la foto fue rechazada, no durante el ajuste
    # normal de manchas (ADR-023).
    ParameterSpec(
        key="min_tissue_fraction",
        label="Tejido de hoja mínimo",
        help=(
            "Fracción del recorte con color de tejido de hoja, del verde al ocre. "
            "Bajarlo admite hojas más secas; subirlo exige una hoja con más croma."
        ),
        group="compuerta",
        minimum=0.0,
        maximum=1.0,
        step=0.01,
        default=0.45,
        unit="del recorte",
    ),
    ParameterSpec(
        key="max_bright_fraction",
        label="Brillo admitido",
        help=(
            "Fracción de píxeles casi blancos que se tolera dentro del recorte. "
            "Subirlo deja pasar hojas con reflejo o fondo quemado."
        ),
        group="compuerta",
        minimum=0.0,
        maximum=1.0,
        step=0.01,
        default=0.30,
        unit="del recorte",
    ),
    ParameterSpec(
        key="min_local_variance",
        label="Textura mínima",
        help=(
            "Varianza local por debajo de la cual el recorte es una superficie "
            "lisa, no tejido. Bajarlo admite hojas muy parejas o fuera de foco."
        ),
        group="compuerta",
        minimum=0.0,
        maximum=200.0,
        step=0.5,
        default=2.0,
        unit="varianza",
    ),
    ParameterSpec(
        key="max_local_variance",
        label="Textura máxima",
        help=(
            "Varianza local por encima de la cual el recorte es ruido y no "
            "tejido. Se mide a 600 px del lado menor, así no depende de la "
            "resolución del archivo."
        ),
        group="compuerta",
        minimum=10.0,
        maximum=2000.0,
        step=10.0,
        default=400.0,
        unit="varianza",
    ),
    ParameterSpec(
        key="min_entropy",
        label="Entropía mínima",
        help=(
            "Bits de detalle del recorte. Por debajo, la imagen es una mancha "
            "plana: ni nervaduras ni lesiones que medir."
        ),
        group="compuerta",
        minimum=0.0,
        maximum=8.0,
        step=0.1,
        default=5.5,
        unit="bits",
    ),
    ParameterSpec(
        key="max_entropy",
        label="Entropía máxima",
        help="Bits de detalle por encima de los cuales lo que hay es ruido.",
        group="compuerta",
        minimum=0.0,
        maximum=8.0,
        step=0.1,
        default=8.0,
        unit="bits",
    ),
    ParameterSpec(
        key="allowed_violations",
        label="Faltas toleradas",
        help=(
            "Cuántos rasgos pueden quedar fuera de la envolvente antes de "
            "rechazar la imagen. 0 exige que cumpla todo."
        ),
        group="compuerta",
        minimum=0.0,
        maximum=6.0,
        step=1.0,
        default=1.0,
        unit="rasgos",
        integer=True,
    ),
)

SPECS: dict[str, ParameterSpec] = {spec.key: spec for spec in PARAMETERS}

# La compuerta vive anidada en ``PipelineSettings.domain_thresholds``: son umbrales
# del veredicto de entrada, no del método de medición.
GATE_FIELDS = frozenset(
    spec.key for spec in PARAMETERS if spec.group == "compuerta"
)

# Campos de ``PipelineSettings`` que se tocan desde este catálogo. Las claves de
# ``Tuning`` son las mismas que las del catálogo público.
TUNABLE_FIELDS = tuple(spec.key for spec in PARAMETERS)

# Enteros: el crecimiento de una mancha se cuenta en píxeles y el kernel de
# morfología tampoco admite fracciones.
_INTEGER_FIELDS = frozenset(spec.key for spec in PARAMETERS if spec.integer)
# De esos, solo el kernel exige lado impar: 8 px de crecimiento es un valor tan
# válido como 9, pero un elemento estructurante de 8 no existe.
_ODD_FIELDS = frozenset({"vein_kernel"})


@dataclass(frozen=True)
class Tuning:
    """Solo lo que el operario cambió. ``None`` significa «usá el defecto»."""

    redness_threshold: float | None = None
    darkness_threshold: float | None = None
    min_lesion_area_fraction: float | None = None
    hysteresis_max_growth_px: float | None = None
    vein_percentile: float | None = None
    vein_kernel: float | None = None
    chlorosis_hue_threshold: float | None = None
    core2_redness_threshold: float | None = None
    core2_darkness_threshold: float | None = None
    core2_chlorosis_yellow_threshold: float | None = None
    core2_chlorosis_green_balance_max: float | None = None
    isolation_sensitivity: float | None = None
    min_sharpness: float | None = None
    min_tissue_fraction: float | None = None
    max_bright_fraction: float | None = None
    min_local_variance: float | None = None
    max_local_variance: float | None = None
    min_entropy: float | None = None
    max_entropy: float | None = None
    allowed_violations: float | None = None

    def __post_init__(self) -> None:
        unknown = [f.name for f in fields(self) if f.name not in SPECS]
        if unknown:  # pragma: no cover - protege contra un catálogo mal editado
            raise InvalidTuning(f"Umbrales sin ficha: {', '.join(unknown)}.")
        for field in fields(self):
            value = getattr(self, field.name)
            if value is None:
                continue
            spec = SPECS[field.name]
            number = _number(value, spec)
            if not spec.minimum <= number <= spec.maximum:
                raise InvalidTuning(
                    f"«{spec.label}» debe estar entre {spec.minimum:g} y "
                    f"{spec.maximum:g}; llegó {number:g}."
                )

    # -- Construcción ----------------------------------------------------
    @classmethod
    def from_mapping(cls, raw: dict[str, Any]) -> Tuning:
        """Toma solo las claves conocidas y deja el resto como defecto."""
        if not isinstance(raw, dict):
            raise InvalidTuning("Los umbrales deben viajar como un objeto JSON.")
        unknown = sorted(set(raw) - set(SPECS))
        if unknown:
            raise InvalidTuning(f"Umbral desconocido: {', '.join(unknown)}.")
        values = {
            key: _number(raw[key], SPECS[key]) for key in raw if raw[key] is not None
        }
        return cls(**values)

    @classmethod
    def from_json(cls, raw: str | None) -> Tuning:
        """Acepta el campo de formulario tal como llega del cliente."""
        # El BOM aparece cuando alguien guarda el JSON con el Bloc de notas de
        # Windows y lo manda por formulario; ``json.loads`` lo rechaza.
        text = (raw or "").lstrip("\ufeff").strip()
        if not text:
            return cls()
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            raise InvalidTuning("Los umbrales no son un JSON válido.") from exc
        return cls.from_mapping(parsed)

    @classmethod
    def from_public(cls, raw: dict[str, Any] | None) -> Tuning:
        """Reconstruye el ajuste guardado en un registro ya persistido."""
        if not raw:
            return cls()
        known = {key: raw[key] for key in raw if key in SPECS}
        return cls(**{key: _number(value, SPECS[key]) for key, value in known.items()})

    # -- Uso -------------------------------------------------------------
    def changed(self) -> dict[str, float | int]:
        """Solo los valores efectivamente movidos, con su tipo final."""
        return {
            field.name: _final(field.name, getattr(self, field.name))
            for field in fields(self)
            if getattr(self, field.name) is not None
        }

    def to_settings(self, base: PipelineSettings | None = None) -> PipelineSettings:
        """Aplica el ajuste sobre los defectos (o sobre una base dada).

        Los umbrales de la compuerta se anidan en ``domain_thresholds``; el resto
        se aplica en la raíz. La combinación se valida al construir
        ``DomainThresholds``: un rango invertido sale como ``InvalidTuning`` y no
        como error interno.
        """
        settings = base or PipelineSettings()
        plain, gate = self._split()
        try:
            if gate:
                settings = replace(
                    settings,
                    domain_thresholds=replace(settings.domain_thresholds, **gate),
                )
            return replace(settings, **plain) if plain else settings
        except ValueError as exc:
            raise InvalidTuning(f"Combinación de umbrales inválida: {exc}") from exc

    def is_default(self) -> bool:
        return not self.changed()

    def validate_for_method(self, method: str) -> Tuning:
        """Reject method-specific controls belonging to the other segmenter."""
        if method not in {"core", "core2"}:
            raise InvalidTuning(f"Método de segmentación desconocido: {method!r}.")
        allowed_prefix = "core2_" if method == "core2" else "core_"
        incompatible = [
            key
            for key in self.changed()
            if SPECS[key].group.startswith(("core_", "core2_"))
            and not SPECS[key].group.startswith(allowed_prefix)
        ]
        if incompatible:
            raise InvalidTuning(
                f"Estos umbrales no corresponden a {method}: {', '.join(incompatible)}."
            )
        return self

    def _split(self) -> tuple[dict[str, float | int], dict[str, float | int]]:
        """Separa lo que va a la raíz de lo que va anidado en la compuerta."""
        values = self.changed()
        gate = {key: value for key, value in values.items() if key in GATE_FIELDS}
        plain = {key: value for key, value in values.items() if key not in GATE_FIELDS}
        return plain, gate


def _number(value: Any, spec: ParameterSpec) -> float:
    """Convierte a número y rechaza texto, NaN o infinito con mensaje legible."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise InvalidTuning(f"«{spec.label}» debe ser un número.")
    number = float(value)
    if number != number or number in (float("inf"), float("-inf")):
        raise InvalidTuning(f"«{spec.label}» debe ser un número finito.")
    return number


def _final(key: str, value: float | None) -> float | int:
    number = _number(value, SPECS[key])
    if key not in _INTEGER_FIELDS:
        return number
    rounded = int(round(number))
    # Solo el kernel se redondea hacia arriba al impar siguiente: el crecimiento
    # de una mancha conserva el par que pidió el operario.
    if key in _ODD_FIELDS and rounded % 2 == 0:
        return rounded + 1
    return rounded


def catalogue() -> list[dict[str, Any]]:
    """Fichas para la pantalla: rango, defecto y explicación de cada umbral."""
    return [spec.to_dict() for spec in PARAMETERS]


def defaults() -> dict[str, float | int]:
    """Valores por defecto resueltos desde ``PipelineSettings``."""
    base = PipelineSettings()
    return {
        spec.key: _final(spec.key, _setting(base, spec.key)) for spec in PARAMETERS
    }


def _setting(settings: PipelineSettings, key: str) -> float:
    """Ubica el defecto de un parámetro, anidado o en la raíz del ajuste."""
    if key in GATE_FIELDS:
        return float(getattr(settings.domain_thresholds, key))
    return float(getattr(settings, key))
