"""Pure reference rebinding and drift detection; server data comparisons live in test_examples."""
import copy
import json

import pytest

from tests.integration.test_examples.references import params_fingerprint, reference_context


@pytest.fixture
def source():
    return {"id": 7, "uuid": "example-table", "slice_name": "Table", "viz_type": "table",
            "datasource_id": 42, "datasource_type": "table",
            "params": json.dumps({"datasource": "99__table", "metrics": ["count"], "slice_id": 7})}


@pytest.fixture
def captures(source):
    return {source["uuid"]: {"slice_name": "Table", "viz_type": "table",
                             "params_sha256": params_fingerprint(source),
                             "query_context": {"datasource": {"type": "table"},
                                               "form_data": {"metrics": ["count"]},
                                               "queries": [{"metrics": ["count"], "filters": [
                                                   {"col": "region", "op": "==", "val": "North"}]}]}}}


def test_rebinding_keeps_the_frontend_query_and_does_not_mutate_the_capture(source, captures):
    before = copy.deepcopy(captures)

    context = reference_context(source, captures)

    assert context["datasource"] == {"id": 42, "type": "table"}
    assert context["form_data"]["datasource"] == "42__table"
    assert "slice_id" not in context["form_data"]
    assert context["queries"] == before["example-table"]["query_context"]["queries"]
    context["queries"][0]["filters"].clear()
    assert captures == before


def test_another_chart_of_the_same_type_cannot_reuse_the_reference(source, captures):
    source["uuid"] = "another-table"

    with pytest.raises(AssertionError, match="No frontend query capture"):
        reference_context(source, captures)


def test_changed_metrics_require_a_new_frontend_capture(source, captures):
    source["params"] = json.dumps({"metrics": ["sum__sales"]})

    with pytest.raises(AssertionError, match="Stale frontend query capture"):
        reference_context(source, captures)


def test_capture_fingerprint_is_portable_between_test_stacks(source, captures):
    source["params"] = json.dumps({"datasource": "101__table", "metrics": ["count"],
                                   "slice_id": 88, "dashboards": [12], "url_params": {"foo": "bar"}})

    assert reference_context(source, captures)["queries"][0]["metrics"] == ["count"]
