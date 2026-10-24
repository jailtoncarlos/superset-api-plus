"""Contract of SerializableModel: per-instance state, equality, and what to_dict serializes."""
from dataclasses import dataclass, field

from supersetapiplus.core.model import SerializableModel
from supersetapiplus.core.fields import object_field
from supersetapiplus.charts.types import ChartType
from supersetapiplus.core.typing import SerializableOptional


@dataclass
class Child(SerializableModel):
    a: int = 1

    @property
    def b(self) -> str:
        return "not a field"


@dataclass
class Parent(SerializableModel):
    b: int = 2
    child: Child = object_field(cls=Child, default_factory=Child)
    values: SerializableOptional[list] = field(default=None)


def test_extra_fields_are_not_shared_between_instances():
    first, second = Parent(), Parent()

    first.extra_fields["only_first"] = 1

    assert "only_first" not in second.extra_fields
    assert dict(SerializableModel._extra_fields) == {}


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
