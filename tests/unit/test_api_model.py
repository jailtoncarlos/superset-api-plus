"""Contract of ApiModel, the pydantic base of the models (#318): the rules of the dataclass engine it replaces.

Reading what Superset stored never loses or changes data; writing leaves out what was absent or is unset; checks
meant for objects built in code are skipped for objects read; JSON text fields and the checks before sending.
"""
import json
from typing import Any, ClassVar

import pytest
from pydantic import Field

from supersetapiplus.charts.types import ChartType, LabelRotation
from supersetapiplus.core.api_model import ApiModel
from supersetapiplus.core.sentinels import MissingField
from supersetapiplus.core.typing import SerializableNotToJson, SerializableOptional
from supersetapiplus.exceptions import LoadJsonError, ValidationError


class Child(ApiModel):
    size: int = 1
    chart: ChartType = ChartType.PIE

    def validate(self) -> None:  # type: ignore[override]
        super().validate()
        if self.size < 0 and not self._read_from_superset:
            raise ValidationError(message="size cannot be negative.", solution="")


class Parent(ApiModel):
    JSON_FIELDS: ClassVar[list[str]] = ["blob"]

    title: str = ""
    ratio: float = 0.5
    rotation: LabelRotation = LabelRotation.ZERO
    child: Child = Field(default_factory=Child)
    children: dict[str, Child] = Field(default_factory=dict)
    note: SerializableOptional[str] = None
    secret: SerializableNotToJson[str] = "hidden"
    blob: SerializableOptional[dict[str, Any]] = None


class Strict(Parent):
    PRESERVE_EXTRA_FIELDS: ClassVar[bool] = False


class Required(ApiModel):
    key: str
    value: int


def test_reading_keeps_values_of_another_type_and_does_not_convert_scalars():
    stored = {"title": 7, "ratio": 5, "rotation": 45, "child": {"size": "10", "chart": "unknown_plugin"}}

    parent = Parent.from_json(stored)

    assert (parent.title, parent.ratio, parent.child.size, parent.child.chart) == (7, 5, "10", "unknown_plugin")
    assert type(parent.ratio) is int and type(parent.rotation) is int  # 5 is not written back as 5.0
    assert parent.to_dict() == {**stored, "blob": {}}  # JSON_FIELDS default to {} as in the dataclass engine


def test_absent_keys_stay_absent_and_unmodeled_keys_are_kept():
    parent = Parent.from_json({"title": "T", "child": {"extra_key": [1]}, "unknown": {"a": None}})

    assert isinstance(parent.ratio, MissingField) and isinstance(parent.child.size, MissingField)
    assert parent.to_dict() == {"title": "T", "child": {"extra_key": [1]}, "blob": {}, "unknown": {"a": None}}
    assert Strict.from_json({"title": "T", "unknown": 1}).to_dict() == {"title": "T", "blob": {}}


def test_a_required_field_absent_from_the_stored_data_stays_absent():
    read = Required.from_json({"key": "k"})

    assert isinstance(read.value, MissingField) and read.to_dict() == {"key": "k"}


def test_nested_models_are_built_and_flagged_as_read():
    parent = Parent.from_json({"children": {"1": {"size": 3}}})

    assert isinstance(parent.children["1"], Child) and parent.children["1"].size == 3
    assert parent._read_from_superset and parent.children["1"]._read_from_superset
    assert not Parent()._read_from_superset


def test_new_object_writes_its_defaults_except_unset_optional_and_not_to_json_fields():
    parent = Parent(note=None, rotation=LabelRotation.NINETY)

    assert parent.to_dict() == {"title": "", "ratio": 0.5, "rotation": 90, "child": {"size": 1, "chart": "pie"},
                                "children": {}, "blob": {}}
    parent.note = "n"
    assert parent.to_dict()["note"] == "n"


def test_json_fields_are_decoded_on_read_and_written_as_text():
    parent = Parent.from_json({"blob": json.dumps({"k": [1]})})

    assert parent.blob == {"k": [1]}
    assert json.loads(parent.to_json()["blob"]) == {"k": [1]}
    assert Parent.from_json({"blob": "null"}).to_json()["blob"] == "{}"  # None becomes {}, as before


def test_checks_before_sending_raise_the_library_errors_and_skip_objects_read():
    built = Parent(child=Child(size=-1))
    with pytest.raises(ValidationError, match="size cannot be negative"):
        built.to_json()

    assert Parent.from_json({"child": {"size": -1}}).to_json()["child"] == {"size": -1}


def test_equality_is_field_by_field_and_ignores_extra_fields():
    first, second = Parent.from_json({"title": "T", "x": 1}), Parent.from_json({"title": "T", "x": 2})

    assert first == second and first != Parent.from_json({"title": "U"})
    with pytest.raises(TypeError):
        hash(first)


def test_invalid_input_raises_load_json_error():
    with pytest.raises(LoadJsonError):
        Parent.from_json({"title": object()})
