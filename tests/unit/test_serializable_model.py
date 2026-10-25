"""Contract of the model base (ApiModel, formerly SerializableModel): per-instance state, equality, and what to_dict
serializes."""
import json
import os
import subprocess
import sys
from pydantic import Field

from supersetapiplus.core.api_model import ApiModel
from supersetapiplus.core.model import ObjectDecoder
from supersetapiplus.charts.types import ChartType, LabelRotation
from supersetapiplus.core.typing import SerializableOptional


class Child(ApiModel):
    a: int = 1

    @property
    def b(self) -> str:
        return "not a field"


class Parent(ApiModel):
    b: int = 2
    child: Child = Field(default_factory=Child)
    values: SerializableOptional[list] = None


def test_extra_fields_are_not_shared_between_instances():
    first, second = Parent(), Parent()

    first.extra_fields["only_first"] = 1

    assert "only_first" not in second.extra_fields


def test_nested_models_serialize_their_own_fields_only():
    # The parent field names used to be passed down as columns: the child's property `b` leaked in.
    assert Parent().to_dict()["child"] == {"a": 1}


def test_an_optional_list_is_judged_as_a_whole_not_by_its_first_item():
    # The first item (None) used to decide for the list, and the field was dropped.
    assert Parent(values=[None, 1]).to_dict()["values"] == [None, 1]
    assert "values" not in Parent().to_dict()


def test_equality_is_field_by_field_and_ignores_extra_fields():
    first, second = Parent.from_json({"b": 3, "unknown": 1}), Parent.from_json({"b": 3})

    assert first == second
    assert Parent(b=3) != Parent(b=4)


def test_string_enum_members_are_their_string_values():
    assert ChartType.PIE == "pie" and {ChartType.PIE: 1}["pie"] == 1
    assert isinstance(ChartType.PIE, str) and str(ChartType.PIE) == f"{ChartType.PIE}" == "pie"


class WithIntEnums(ApiModel):
    rotation: SerializableOptional[LabelRotation] = None
    rotations: list[LabelRotation] = Field(default_factory=list)


def test_integer_enum_members_are_written_as_numbers():
    """Superset stores these controls as numbers (xAxisLabelRotation 45, a funnel label_type 0, a column's
    type_generic 1); writing the text "45" sent a value of another type than the UI sends."""
    model = WithIntEnums(rotation=LabelRotation.FORTY_FIVE, rotations=[LabelRotation.NINETY])

    assert model.to_dict() == {"rotation": 45, "rotations": [90]}
    assert json.loads(json.dumps(LabelRotation.ZERO, cls=ObjectDecoder)) == 0
    assert json.loads(json.dumps(ChartType.PIE, cls=ObjectDecoder)) == "pie"


def test_fields_are_written_in_declaration_order_whatever_the_hash_seed():
    """The query of some plugins depends on the form_data key order (Bubble lists the x, y and size metrics in
    that order): iterating over a set of field names gave a different order in each Python process."""
    script = ("from tests.unit.test_serializable_model import Parent; "
              "print(list(Parent(values=[1]).to_dict(columns=['extra'])))")
    orders = {subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, check=True,
                             env={**os.environ, "PYTHONHASHSEED": seed}).stdout for seed in ("1", "2", "3", "4")}

    assert orders == {"['b', 'child', 'values']\n"}


def test_models_work_without_a_client_and_fail_clearly_when_asked_to_reach_the_server():
    from supersetapiplus.dashboards.dashboards import Dashboard
    from supersetapiplus.exceptions import UnboundModelError

    dashboard = Dashboard(dashboard_title="Offline")
    assert dashboard.to_json()["dashboard_title"] == "Offline"

    for call in (dashboard.save, dashboard.fetch, dashboard.delete, lambda: dashboard.base_url):
        try:
            call()
        except UnboundModelError as error:
            assert "client" in str(error)
        else:
            raise AssertionError("expected UnboundModelError")
