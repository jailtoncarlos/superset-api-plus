"""TableChart.fix_label_column_width: the label column gets the width the sizing profile was calibrated with, so a
table placed with TableContent(fixed_label_width=True) is estimated as drawn. Pure logic, no HTTP."""
import pytest

from supersetapiplus.charts.queries import ColumnConfig
from supersetapiplus.charts.table import TableChart
from supersetapiplus.core.datasource import DataSource
from supersetapiplus.dashboards.layout.sizing import calibrated_profile

PROFILE = calibrated_profile()


def table() -> TableChart:
    chart = TableChart.instance(slice_name="By campus", datasource=DataSource(id=1, type="table"))
    chart.add_simple_dimension("campus")
    chart.add_simple_metric("count")
    return chart


def test_the_label_column_gets_the_width_of_the_profile_in_params_and_form_data():
    chart = table()
    width = chart.fix_label_column_width("campus")
    assert width == PROFILE.table.label_column_width == 560
    for target in (chart.params, chart.query_context.form_data):
        assert target.to_dict()["column_config"] == {"campus": {"columnWidth": 560}}


def test_the_other_settings_of_the_column_are_kept():
    chart = table()
    chart.params._add_column_config("campus", ColumnConfig.from_json({"columnWidth": 100, "horizontalAlign": "left"}))
    chart.fix_label_column_width("campus")
    assert chart.params.to_dict()["column_config"] == {"campus": {"columnWidth": 560, "horizontalAlign": "left"}}


def test_another_profile_gives_its_own_width_and_one_without_it_is_refused():
    wider = PROFILE.model_copy(update={"table": PROFILE.table.model_copy(update={"label_column_width": 640.4})})
    assert table().fix_label_column_width("campus", wider) == 640
    unknown = PROFILE.model_copy(update={"table": PROFILE.table.model_copy(update={"label_column_width": None})})
    with pytest.raises(ValueError, match="label column width"):
        table().fix_label_column_width("campus", unknown)
