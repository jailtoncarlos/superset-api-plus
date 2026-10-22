"""Gera as referências de gráficos salvos pelo Superset (tests/fixtures/referencias_ui_<versão>).

Determinístico para a mesma versão: os exemplos vêm do próprio pacote do Superset.

Lê de uma instância com os exemplos públicos carregados (ex.: a stack de testes com
SUPERSET_LOAD_EXAMPLES=1) um gráfico por viz_type, localizado pelo título e pelo tipo (os ids
mudam de instância para instância), e grava só os campos usados na modelagem, sem os que
dependem da instância ou do momento (ids, URLs, miniaturas, "há 11 meses").

Uso:
    SUPERSET_URL=... SUPERSET_USERNAME=... SUPERSET_PASSWORD=... \\
        python bin/scripts/extrair_referencias_ui.py 6.1.0
"""
import json
import os
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))

from supersetapiplus.client import SupersetClient  # noqa: E402
from supersetapiplus.query_string import QueryOperator, QueryStringFilter  # noqa: E402

# viz_type -> título do gráfico no conjunto "um gráfico por tipo" dos exemplos do Superset
# (`superset load_examples`). cal_heatmap não existe nos exemplos.
GRAFICOS = {
    "big_number_total": "Big Number",
    "box_plot": "Box Plot",
    "echarts_timeseries_bar": "Bar",
    "mixed_timeseries": "Mixed",
    "pie": "Pie",
    "pivot_table_v2": "Pivot Table",
    "table": "Table",
    "word_cloud": "Word Cloud",
}

CAMPOS = ("slice_name", "viz_type", "params", "query_context", "datasource_type", "datasource_name_text",
          "description", "cache_timeout")


def gravar_json(caminho: Path, dados) -> None:
    caminho.write_text(json.dumps(dados, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")


def main(versao: str) -> None:
    client = SupersetClient(os.environ["SUPERSET_URL"], os.environ["SUPERSET_USERNAME"],
                            os.environ["SUPERSET_PASSWORD"])
    client.enable_session_mode()
    destino = RAIZ / "tests" / "fixtures" / f"referencias_ui_{versao}"
    destino.mkdir(parents=True, exist_ok=True)

    indice = {}
    for viz_type, titulo in GRAFICOS.items():
        filtro = QueryStringFilter()
        filtro.add("slice_name", QueryOperator.EQUAL, titulo)
        filtro.add("viz_type", QueryOperator.EQUAL, viz_type)
        resposta = client.find(client.charts.base_url, filtro, ["id"], page_size=2).json()
        if resposta["count"] != 1:
            print(f"{viz_type}: {resposta['count']} gráficos '{titulo}' — pulado", file=sys.stderr)
            continue
        chart_id = resposta["result"][0]["id"]
        resultado = client.get(client.join_urls(client.charts.base_url, chart_id)).json()["result"]
        gravar_json(destino / f"{viz_type}.json", {campo: resultado.get(campo) for campo in CAMPOS})
        indice[viz_type] = {"slice_name": titulo, "dataset": resultado.get("datasource_name_text"),
                            "query_context": "presente" if resultado.get("query_context") else "nulo"}

    gravar_json(destino / "INDICE.json", indice)
    print(f"{len(indice)} referências em {destino}", file=sys.stderr)


if __name__ == "__main__":
    main(sys.argv[1])
