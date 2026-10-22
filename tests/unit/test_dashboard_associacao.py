"""Associação gráfico ↔ dashboard, dados do gráfico, remoção e posicionamento no layout."""
import json

import pytest
import requests_mock as rm

from supersetapiplus.base.base import UnsupportedObject
from supersetapiplus.charts.table import TableChart
from supersetapiplus.client import SupersetClient
from supersetapiplus.dashboards.dashboards import Dashboard
from supersetapiplus.dashboards.itemposition import ItemPositionType, MarkdownItemPosition
from supersetapiplus.dashboards.metadataposition import Metadataposition
from supersetapiplus.exceptions import DashboardValidationError, NodePositionValidationError, NotFound

HOST = "https://superset.exemplo"
API = f"{HOST}/api/v1"
PARAMS = {"datasource": "1__table", "viz_type": "table", "query_mode": "aggregate", "groupby": ["campus"],
          "metrics": ["count"]}


def chart_json(chart_id: int, dashboards=(), viz_type="table") -> dict:
    return {"id": chart_id, "slice_name": f"G{chart_id}", "viz_type": viz_type, "params": json.dumps(PARAMS),
            "query_context": None, "dashboards": [{"id": d, "dashboard_title": f"D{d}"} for d in dashboards]}


@pytest.fixture
def mock():
    with rm.Mocker() as m:
        m.post(f"{API}/security/login", json={"access_token": "t"})
        m.get(f"{API}/security/csrf_token/", json={"result": "c"})
        m.get(f"{API}/chart/_info", json={})
        m.get(f"{API}/dashboard/_info", json={})
        yield m


@pytest.fixture
def client(mock):
    return SupersetClient(HOST, "robo", "senha")


def puts(mock, path):
    return [r.json() for r in mock.request_history if r.method == "PUT" and r.path == path]


def test_add_to_dashboard_acrescenta_mantendo_as_associacoes_existentes(client, mock):
    mock.get(f"{API}/chart/9", json={"id": 9, "result": chart_json(9, dashboards=[3])})
    mock.put(f"{API}/chart/9", json={"id": 9, "result": {}})

    assert client.charts.add_to_dashboard(9, 5) == [3, 5]
    assert puts(mock, "/api/v1/chart/9") == [{"dashboards": [3, 5]}]


def test_add_to_dashboard_ja_associado_nao_regrava(client, mock):
    mock.get(f"{API}/chart/9", json={"id": 9, "result": chart_json(9, dashboards=[5])})

    assert client.charts.add_to_dashboard(9, 5) == [5]
    assert puts(mock, "/api/v1/chart/9") == []


def test_attach_charts_associa_todos_os_graficos_do_layout(client, mock):
    dashboard = Dashboard(dashboard_title="Painel", id=5)
    aba = dashboard.position.add_tab("Aba")
    for chart_id in (1, 2):
        dashboard.position.add_chart(TableChart(slice_name=f"G{chart_id}", id=chart_id), f"G{chart_id}", parent=aba)
        mock.get(f"{API}/chart/{chart_id}", json={"id": chart_id, "result": chart_json(chart_id)})
        mock.put(f"{API}/chart/{chart_id}", json={"result": {}})

    assert client.dashboards.attach_charts(dashboard) == [1, 2]
    assert puts(mock, "/api/v1/chart/1") == [{"dashboards": [5]}] and puts(mock, "/api/v1/chart/2") == [{"dashboards": [5]}]


def test_add_chart_exige_dashboard_salvo_antes_de_qualquer_requisicao(client, mock):
    dashboard = client.dashboards.get_base_object()(dashboard_title="Novo")
    dashboard._factory = client.dashboards

    with pytest.raises(DashboardValidationError):
        dashboard.add_chart(TableChart(slice_name="G", datasource_id=1), "G")
    assert [r for r in mock.request_history if r.method in ("POST", "PUT") and "/chart/" in r.path] == []


def test_add_chart_cria_o_grafico_poe_no_layout_e_associa(client, mock):
    dashboard = Dashboard(dashboard_title="Painel", id=5)
    dashboard._factory = client.dashboards
    chart = TableChart.from_json(chart_json(None) | {"datasource_id": 1, "datasource_type": "table"})
    mock.post(f"{API}/chart/", json={"id": 9, "result": {}})
    mock.get(f"{API}/chart/9", json={"id": 9, "result": chart_json(9)})
    mock.put(f"{API}/chart/9", json={"result": {}})

    dashboard.add_chart(chart, "Título no painel")

    assert chart.id == 9
    assert dashboard.position.tree.chart_ids() == [9]
    assert puts(mock, "/api/v1/chart/9") == [{"dashboards": [5]}]


def test_get_charts_usa_a_rota_do_dashboard_e_tolera_tipo_sem_modelo(client, mock):
    mock.get(f"{API}/dashboard/5", json={"id": 5, "result": {"id": 5, "dashboard_title": "P"}})
    mock.get(f"{API}/dashboard/5/charts", json={"result": [{"id": 1, "slice_name": "a", "viz_type": "table"},
                                                           {"id": 2, "slice_name": "b", "viz_type": "histogram_v2"}]})
    mock.get(f"{API}/chart/1", json={"id": 1, "result": chart_json(1)})
    mock.get(f"{API}/chart/2", json={"id": 2, "result": chart_json(2, viz_type="histogram_v2")})

    charts = client.dashboards.get(5).get_charts()

    assert type(charts[0]).__name__ == "TableChart" and isinstance(charts[1], UnsupportedObject)


def test_delete_devolve_bool_e_remove_graficos_quando_pedido(client, mock):
    mock.get(f"{API}/dashboard/5", json={"id": 5, "result": {"id": 5, "dashboard_title": "P"}})
    mock.get(f"{API}/dashboard/5/charts", json={"result": [{"id": 1}]})
    mock.get(f"{API}/chart/1", json={"id": 1, "result": chart_json(1)})
    mock.delete(f"{API}/dashboard/5", json={"message": "OK"})
    mock.delete(f"{API}/chart/1", json={"message": "OK"})

    assert client.dashboards.get(5).delete(exclude_charts=True) is True
    assert [r.path for r in mock.request_history if r.method == "DELETE"] == ["/api/v1/dashboard/5", "/api/v1/chart/1"]


def test_get_chart_data_usa_o_query_context_salvo_e_confere_o_dashboard(client, mock):
    mock.get(f"{API}/chart/9", json={"id": 9, "result": chart_json(9, dashboards=[5])})
    mock.get(f"{API}/chart/9/data/", json={"result": [{"rowcount": 2, "data": [{"campus": "Natal", "count": 3}]}]})

    assert client.charts.get_chart_data(9, dashboard_id=5)[0]["rowcount"] == 2
    with pytest.raises(NotFound):
        client.charts.get_chart_data(9, dashboard_id=7)


def test_add_and_attach_valida_antes_de_criar_o_grafico(client, mock):
    chart = TableChart.from_json(chart_json(None) | {"datasource_id": 1, "datasource_type": "table"})

    with pytest.raises(DashboardValidationError):
        client.charts.add_and_attach_to_dashboard(chart, "Título")
    assert not any(r.method == "POST" and r.path == "/api/v1/chart/" for r in mock.request_history)


# --- Posicionamento no layout ----------------------------------------------------------------

def test_linha_cheia_sem_relocate_levanta_e_com_relocate_abre_linha_nova():
    pos = Metadataposition()
    aba = pos.add_tab("Aba")
    primeiro = pos.add_markdown("a", parent=aba, width=8)
    linha = primeiro.parent

    with pytest.raises(NodePositionValidationError):
        pos.add_markdown("b", parent=linha, width=8, relocate=False)

    segundo = pos.add_markdown("c", parent=linha, width=8)
    assert segundo.parent is not linha and segundo.parent.type_ == ItemPositionType.ROW


def test_item_vai_para_linha_irma_com_espaco():
    pos = Metadataposition()
    aba = pos.add_tab("Aba")
    linha_cheia = pos.add_markdown("a", parent=aba, width=12).parent
    linha_livre = pos.add_markdown("b", parent=aba, width=4).parent

    novo = pos.add_markdown("c", parent=linha_cheia, width=4)

    assert novo.parent is linha_livre


def test_validate_do_pie_aceita_grafico_criado_por_codigo_e_recusa_orderby_que_nao_e_par():
    from supersetapiplus.base.datasource import DataSource
    from supersetapiplus.charts.pie import PieChart
    from supersetapiplus.exceptions import ValidationError

    chart = PieChart.instance(slice_name="p", datasource=DataSource(id=1, type="table"))
    chart.add_simple_metric("count")
    chart.add_simple_dimension("campus")
    chart.validate()

    chart.query_context.queries[0].orderby = [["count", True]]
    with pytest.raises(ValidationError, match="tuple"):
        chart.query_context.validate()


def test_markdown_item_position_continua_disponivel():
    assert MarkdownItemPosition(code="x").width == 4
