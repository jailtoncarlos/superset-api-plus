"""Legacy layout placement (MetadataPosition/ItemPosition) and pie validation, without HTTP."""
import pytest

from supersetapiplus.dashboards.layout.legacy.items import ItemPositionType, MarkdownItemPosition
from supersetapiplus.dashboards.layout.legacy.metadata_position import MetadataPosition
from supersetapiplus.exceptions import NodePositionValidationError

# --- Layout placement ----------------------------------------------------------------------

def test_full_row_raises_without_relocate_and_opens_new_row_with_relocate():
    pos = MetadataPosition()
    tab = pos.add_tab("Tab")
    first = pos.add_markdown("a", parent=tab, width=8)
    row = first.parent

    with pytest.raises(NodePositionValidationError):
        pos.add_markdown("b", parent=row, width=8, relocate=False)

    second = pos.add_markdown("c", parent=row, width=8)
    assert second.parent is not row and second.parent.type_ == ItemPositionType.ROW


def test_item_goes_to_sibling_row_with_room():
    pos = MetadataPosition()
    tab = pos.add_tab("Tab")
    full_row = pos.add_markdown("a", parent=tab, width=12).parent
    free_row = pos.add_markdown("b", parent=tab, width=4).parent

    new = pos.add_markdown("c", parent=full_row, width=4)

    assert new.parent is free_row


def test_pie_validate_accepts_chart_created_in_code_and_rejects_non_pair_orderby():
    from supersetapiplus.core.datasource import DataSource
    from supersetapiplus.charts.pie import PieChart
    from supersetapiplus.exceptions import ValidationError

    chart = PieChart.instance(slice_name="p", datasource=DataSource(id=1, type="table"))
    chart.add_simple_metric("count")
    chart.add_simple_dimension("campus")
    chart.validate()

    chart.query_context.queries[0].orderby = [["count", True]]
    with pytest.raises(ValidationError, match="tuple"):
        chart.query_context.validate()


def test_markdown_item_position_is_still_available():
    assert MarkdownItemPosition(code="x").width == 4
