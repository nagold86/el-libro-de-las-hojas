"""Catálogo de umbrales: una sola verdad y validación del formulario (ADR-022).

El catálogo es la única fuente de rangos y defectos. Estos tests vigilan las dos
cosas que se pueden romper sin ruido: que los defectos del catálogo sean los de
``PipelineSettings`` y que lo que llega del cliente se acepte o se rechace con un
mensaje, nunca con un ``ValueError`` suelto.
"""

from __future__ import annotations

import json

import pytest

from core.exceptions import InvalidTuning
from core.pipeline import PipelineSettings, build_pipeline, method_fingerprint
from core.tuning import PARAMETERS, Tuning, catalogue, defaults


def test_defaults_come_from_the_pipeline_settings():
    base = PipelineSettings()
    gate = base.domain_thresholds

    resolved = defaults()

    for key, value in resolved.items():
        # La compuerta vive anidada: su defecto no está en la raíz del ajuste.
        expected = getattr(gate, key) if hasattr(gate, key) else getattr(base, key)
        assert expected == value, key
    # Y no al revés: el catálogo no inventa campos que la configuración no tenga.
    assert set(resolved) == {spec.key for spec in PARAMETERS}
    for spec in PARAMETERS:
        assert hasattr(base, spec.key) or hasattr(gate, spec.key), spec.key


def test_catalogue_is_complete_and_json_ready():
    entries = catalogue()

    assert len(entries) == len(PARAMETERS)
    for entry in entries:
        assert {"key", "label", "help", "group", "min", "max", "step", "default"} <= set(entry)
        assert entry["min"] < entry["max"], entry["key"]
        assert entry["min"] <= entry["default"] <= entry["max"], entry["key"]
        assert entry["step"] > 0, entry["key"]
        assert entry["help"].strip(), entry["key"]
    json.dumps(entries)


def test_every_parameter_belongs_to_a_known_group():
    assert {spec.group for spec in PARAMETERS} <= {
        "manchas",
        "core_lesiones",
        "core_clorosis",
        "core2_lesiones",
        "core2_clorosis",
        "nervaduras",
        "clorosis",
        "aislamiento",
        "calidad",
        "compuerta",
    }


def test_empty_tuning_means_defaults():
    tuning = Tuning.from_json(None)

    assert tuning.is_default()
    assert tuning.changed() == {}
    assert tuning.to_settings() == PipelineSettings()


def test_only_the_moved_value_changes():
    tuning = Tuning.from_json('{"redness_threshold": 0.05}')

    settings = tuning.to_settings()

    assert tuning.changed() == {"redness_threshold": 0.05}
    assert not tuning.is_default()
    assert settings.redness_threshold == 0.05
    assert settings.darkness_threshold == PipelineSettings().darkness_threshold
    assert settings.vein_kernel == PipelineSettings().vein_kernel


def test_core2_controls_reach_the_second_pipeline():
    tuning = Tuning.from_mapping(
        {
            "core2_redness_threshold": 0.12,
            "core2_darkness_threshold": 0.36,
            "core2_chlorosis_yellow_threshold": 0.20,
            "core2_chlorosis_green_balance_max": 0.09,
        }
    )

    pipeline = build_pipeline(tuning.to_settings(), segmentation_method="core2")

    assert pipeline.segmenter.redness_threshold == 0.12
    assert pipeline.segmenter.darkness_threshold == 0.36
    assert pipeline.chlorosis.yellow_threshold == 0.20
    assert pipeline.chlorosis.green_balance_max == 0.09


def test_method_specific_controls_are_not_cross_applied():
    with pytest.raises(InvalidTuning, match="no corresponden"):
        Tuning.from_mapping({"redness_threshold": 0.1}).validate_for_method("core2")
    with pytest.raises(InvalidTuning, match="no corresponden"):
        Tuning.from_mapping({"core2_redness_threshold": 0.1}).validate_for_method("core")


def test_moving_a_threshold_changes_the_method_fingerprint():
    tuned = Tuning.from_json('{"redness_threshold": 0.05}')

    assert method_fingerprint(tuned.to_settings()) != method_fingerprint()
    # Sin mover nada, la huella es la de la aplicación.
    assert method_fingerprint(Tuning().to_settings()) == method_fingerprint()


def test_tuning_never_touches_the_structure_of_the_method():
    settings = Tuning.from_json('{"darkness_threshold": 0}').to_settings()

    # Apagar la segunda evidencia no apaga la histéresis ni la compuerta: eso no
    # se ajusta desde la pantalla.
    assert settings.hysteresis is True
    assert settings.isolation_sensitivity == PipelineSettings().isolation_sensitivity


def test_even_kernel_is_rounded_up_to_odd():
    tuning = Tuning.from_json('{"vein_kernel": 10}')

    assert tuning.changed()["vein_kernel"] == 11
    pipeline = build_pipeline(tuning.to_settings())
    assert pipeline.segmenter.vein_detector.kernel_size == 11


def test_growth_px_stays_an_integer():
    tuning = Tuning.from_json('{"hysteresis_max_growth_px": 12.4}')

    value = tuning.changed()["hysteresis_max_growth_px"]

    assert value == 12
    assert isinstance(value, int)


def test_stored_record_rebuilds_the_same_run():
    tuning = Tuning(redness_threshold=0.07, vein_kernel=15)

    again = Tuning.from_public(json.loads(json.dumps(tuning.changed())))

    assert again.to_settings() == tuning.to_settings()
    assert again.to_settings() == tuning.to_settings()


def test_unknown_keys_in_an_old_record_are_ignored():
    # Un parámetro que se retiró del catálogo no puede romper la descarga de un
    # registro viejo.
    assert Tuning.from_public({"desaparecido": 1}).is_default()


@pytest.mark.parametrize(
    "raw",
    [
        "no es json",
        "[]",
        '"texto"',
        '{"inventado": 1}',
        '{"redness_threshold": "mucho"}',
        '{"redness_threshold": null}',  # null sí se acepta: significa «defecto»
    ],
)
def test_bad_payloads_are_rejected_with_a_message(raw):
    if raw == '{"redness_threshold": null}':
        assert Tuning.from_json(raw).is_default()
        return
    with pytest.raises(InvalidTuning) as excinfo:
        Tuning.from_json(raw)
    assert str(excinfo.value)


@pytest.mark.parametrize(
    "raw",
    [
        '{"redness_threshold": 5}',
        '{"redness_threshold": -1}',
        '{"vein_kernel": 2}',
        '{"vein_percentile": 200}',
        '{"hysteresis_max_growth_px": -1}',
        '{"isolation_sensitivity": 0}',
    ],
)
def test_out_of_range_values_are_rejected(raw):
    with pytest.raises(InvalidTuning):
        Tuning.from_json(raw)


def test_a_bom_from_a_windows_editor_is_tolerated():
    # Guardar el JSON con el Bloc de notas deja un BOM al principio.
    tuning = Tuning.from_json('\ufeff{"redness_threshold": 0.05}')

    assert tuning.changed() == {"redness_threshold": 0.05}


def test_settings_accept_every_catalogue_default():
    # Un ajuste que repite el defecto no cambia la corrida, pero tiene que poder
    # viajar: la pantalla manda el valor del deslizador tal como está.
    tuning = Tuning(**{key: value for key, value in defaults().items()})

    assert tuning.to_settings() == PipelineSettings()


def test_gate_thresholds_land_in_the_domain_envelope():
    tuning = Tuning.from_json('{"min_tissue_fraction": 0.3, "allowed_violations": 2}')
    base = PipelineSettings()

    settings = tuning.to_settings()
    envelope = settings.domain_thresholds

    assert envelope.min_tissue_fraction == 0.3
    assert envelope.allowed_violations == 2
    assert isinstance(envelope.allowed_violations, int)
    # El resto de la envolvente queda como estaba…
    assert envelope.max_local_variance == base.domain_thresholds.max_local_variance
    # …y el método de medición tampoco se movió: solo cambió cuánto se tolera.
    assert settings.redness_threshold == base.redness_threshold


def test_contradictory_gate_thresholds_are_rejected_with_a_message():
    # Cada valor está dentro de su rango, pero juntos invierten la envolvente.
    tuning = Tuning.from_json('{"min_local_variance": 150, "max_local_variance": 100}')

    with pytest.raises(InvalidTuning) as excinfo:
        tuning.to_settings()

    assert "invertido" in str(excinfo.value)
