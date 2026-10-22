"""Dashboard: ida e volta de json_metadata/position_json e consistência do layout montado por código."""
import json

import pytest

from supersetapiplus.charts.table import TableChart
from supersetapiplus.dashboards.dashboards import Dashboard
from supersetapiplus.dashboards.metadataposition import Metadataposition

POSITION = {
    "DASHBOARD_VERSION_KEY": "v2",
    "ROOT_ID": {"id": "ROOT_ID", "type": "ROOT", "children": ["TABS-a"], "parents": []},
    "GRID_ID": {"id": "GRID_ID", "type": "GRID", "children": [], "parents": ["ROOT_ID"]},
    "TABS-a": {"id": "TABS-a", "type": "TABS", "children": ["TAB-1", "TAB-2"], "parents": ["ROOT_ID"], "meta": {}},
    "TAB-1": {"id": "TAB-1", "type": "TAB", "children": ["ROW-1"], "parents": ["ROOT_ID", "TABS-a"],
              "meta": {"text": "Geral", "defaultText": "Tab title", "placeholder": "Tab title"}},
    "TAB-2": {"id": "TAB-2", "type": "TAB", "children": ["MARKDOWN-1", "DIVIDER-1"], "parents": ["ROOT_ID", "TABS-a"],
              "meta": {"text": "Sobre", "defaultText": "Tab title", "placeholder": "Tab title"}},
    "ROW-1": {"id": "ROW-1", "type": "ROW", "children": ["CHART-1", "CHART-2"],
              "parents": ["ROOT_ID", "TABS-a", "TAB-1"], "meta": {"background": "BACKGROUND_TRANSPARENT"}},
    "CHART-1": {"id": "CHART-1", "type": "CHART", "children": [], "parents": ["ROOT_ID", "TABS-a", "TAB-1", "ROW-1"],
                "meta": {"chartId": 11, "height": 50, "sliceName": "A", "uuid": "u-1", "width": 6}},
    "CHART-2": {"id": "CHART-2", "type": "CHART", "children": [], "parents": ["ROOT_ID", "TABS-a", "TAB-1", "ROW-1"],
                "meta": {"chartId": 12, "height": 50, "sliceName": "B", "sliceNameOverride": "B2", "uuid": "u-2",
                         "width": 6}},
    "MARKDOWN-1": {"id": "MARKDOWN-1", "type": "MARKDOWN", "children": [], "parents": ["ROOT_ID", "TABS-a", "TAB-2"],
                   "meta": {"code": "# Texto", "height": 50, "width": 4}},
    "DIVIDER-1": {"id": "DIVIDER-1", "type": "DIVIDER", "children": [], "parents": ["ROOT_ID", "TABS-a", "TAB-2"]},
}

METADATA = {
    "color_scheme": "supersetColors", "refresh_frequency": 0, "label_colors": {"A": "#ffffff"},
    "shared_label_colors": [], "color_scheme_domain": [], "expanded_slices": {}, "timed_refresh_immune_slices": [],
    "cross_filters_enabled": True, "default_filters": "{}", "chart_configuration": {},
    "global_chart_configuration": {"scope": {"rootPath": ["ROOT_ID"], "excluded": []}, "chartsInScope": [11, 12]},
    "native_filter_configuration": [], "map_label_colors": {},
}


def exportado() -> dict:
    return {"id": 5, "dashboard_title": "Painel", "published": True,
            "position_json": json.dumps(POSITION), "json_metadata": json.dumps(METADATA)}


def campo(dashboard: Dashboard, nome: str) -> dict:
    valor = dashboard.to_json()[nome]
    return json.loads(valor) if isinstance(valor, str) else valor


def test_json_metadata_faz_ida_e_volta_sem_perda():
    assert campo(Dashboard.from_json(exportado()), "json_metadata") == METADATA


@pytest.mark.xfail(strict=True, reason="round-trip do position_json: issue #300 (GitLab institucional)")
def test_position_json_faz_ida_e_volta_sem_perda():
    assert campo(Dashboard.from_json(exportado()), "position_json") == POSITION


def test_layout_montado_por_codigo_e_consistente():
    pos = Metadataposition()
    aba = pos.add_tab("Indicadores")
    for chart_id in (1, 2, 3):
        pos.add_chart(TableChart(slice_name=f"G{chart_id}", id=chart_id), f"G{chart_id}", parent=aba, width=6)
    pos.add_markdown("# Notas", parent=aba, width=12)

    layout = pos.to_dict()
    itens = {k: v for k, v in layout.items() if isinstance(v, dict)}

    for item_id, item in itens.items():
        for filho in item["children"]:
            assert filho in itens, f"{item_id} aponta para filho inexistente {filho}"
            assert itens[filho]["parents"] == item["parents"] + [item_id]
    graficos = [i for i in itens.values() if i["type"] == "CHART"]
    assert sorted(g["meta"]["chartId"] for g in graficos) == [1, 2, 3]
    linhas = [i for i in itens.values() if i["type"] == "ROW"]
    assert all(sum(itens[c]["meta"]["width"] for c in linha["children"]) <= 12 for linha in linhas)


def test_cores_do_dashboard_sao_lidas_e_atualizadas_no_json_metadata():
    dashboard = Dashboard.from_json(exportado())

    dashboard.update_colors({"B": "#000000"})

    assert dashboard.colors == {"A": "#ffffff", "B": "#000000"}
    assert campo(dashboard, "json_metadata")["label_colors"] == {"A": "#ffffff", "B": "#000000"}
