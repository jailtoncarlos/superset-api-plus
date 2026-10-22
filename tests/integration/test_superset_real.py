"""Integração contra um Superset real (validado no 6.1.0), autenticando por sessão (cookie + CSRF).

Executar com:
    SUPERSET_URL=http://localhost:8088 SUPERSET_USERNAME=... SUPERSET_PASSWORD=... \
        pytest tests/integration/test_superset_real.py -v

Cria e remove um gráfico e um dashboard de teste (prefixo "zz-superset-api-plus-teste").
"""
import importlib
import os
import uuid

import pytest

from supersetapiplus.client import SupersetClient
from supersetapiplus.dashboards.dashboards import Dashboard
from supersetapiplus.exceptions import UnsupportedTypeError
from supersetapiplus.query_string import QueryOperator, QueryStringFilter

URL, USER, PASSWORD = (os.getenv(v) for v in ("SUPERSET_URL", "SUPERSET_USERNAME", "SUPERSET_PASSWORD"))

pytestmark = pytest.mark.skipif(not (URL and USER and PASSWORD),
                                reason="defina SUPERSET_URL, SUPERSET_USERNAME e SUPERSET_PASSWORD")

PREFIXO = "zz-superset-api-plus-teste"
SUPORTADOS = ["table", "pie", "pivot_table_v2", "echarts_timeseries_bar", "big_number_total",
              "box_plot", "cal_heatmap", "mixed_timeseries", "word_cloud"]


@pytest.fixture(scope="module")
def client():
    client = SupersetClient(URL, USER, PASSWORD, verify=URL.startswith("https"))
    client.enable_session_mode()
    return client


def filtro(column, operator, value):
    f = QueryStringFilter()
    f.add(column, operator, value)
    return f


def ids_por_tipo(client, viz_type, limite=3):
    charts = client.charts.find(filtro("viz_type", QueryOperator.EQUAL, viz_type),
                                columns=["id", "viz_type"], page_size=limite)
    return [c.id for c in charts]


def test_lista_graficos_autenticado_por_sessao(client):
    assert client.charts.count() > 0


@pytest.mark.parametrize("viz_type", SUPORTADOS)
def test_le_e_serializa_graficos_dos_tipos_suportados(client, viz_type):
    importlib.import_module(f"supersetapiplus.charts.{viz_type}")
    ids = ids_por_tipo(client, viz_type)
    if not ids:
        pytest.skip(f"nenhum gráfico {viz_type} nesta instância")

    for chart_id in ids:
        chart = client.charts.get(chart_id)
        dados = chart.to_json()
        assert dados["slice_name"] and str(chart.viz_type) == viz_type


def test_tipo_sem_modelo_e_sinalizado_com_unsupported_type(client):
    tipos = {c.viz_type for c in client.charts.find(QueryStringFilter(), columns=["id", "viz_type"], page_size=100)
             if str(c.viz_type) not in SUPORTADOS}
    if not tipos:
        pytest.skip("todos os gráficos desta instância são de tipos suportados")
    chart_id = ids_por_tipo(client, str(sorted(map(str, tipos))[0]), limite=1)[0]

    with pytest.raises(UnsupportedTypeError):
        client.charts.get(chart_id)


def test_cria_altera_e_remove_grafico(client):
    origem_id = next((i for t in SUPORTADOS for i in ids_por_tipo(client, t, limite=1)), None)
    if origem_id is None:
        pytest.skip("nenhum gráfico de tipo suportado para clonar")
    chart = client.charts.get(origem_id)
    chart.slice_name = f"{PREFIXO}-{uuid.uuid4().hex[:8]}"
    chart.dashboards = []

    novo_id = client.charts.add(chart)
    try:
        assert novo_id and novo_id != origem_id
        criado = client.charts.get(novo_id)
        criado.slice_name = f"{chart.slice_name}-alterado"
        criado.save()
        assert client.charts.get(novo_id).slice_name.endswith("-alterado")
    finally:
        assert client.charts.delete(novo_id)


def test_cria_altera_e_remove_dashboard(client):
    titulo = f"{PREFIXO}-{uuid.uuid4().hex[:8]}"
    dashboard = Dashboard(dashboard_title=titulo)

    novo_id = client.dashboards.add(dashboard)
    try:
        assert novo_id
        criado = client.dashboards.get(novo_id)
        criado.dashboard_title = f"{titulo}-alterado"
        criado.save()
        assert client.dashboards.get(novo_id).dashboard_title.endswith("-alterado")
    finally:
        assert client.dashboards.delete(novo_id)
