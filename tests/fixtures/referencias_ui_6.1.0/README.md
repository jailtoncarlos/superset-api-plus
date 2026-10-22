# Referências de gráficos salvos pelo Superset 6.1.0

Geradas por `bin/scripts/extrair_referencias_ui.py 6.1.0` a partir da stack de testes com os
exemplos públicos do Superset (`SUPERSET_LOAD_EXAMPLES=1`): um gráfico por `viz_type` do conjunto
"um gráfico por tipo" dos exemplos (`Pie`, `Table`, `Bar`...). Só os campos usados na modelagem são
gravados; ids, URLs e campos que mudam com o tempo ficam de fora. `INDICE.json` lista título,
dataset e se há `query_context`. `cal_heatmap` não existe nos exemplos.

Para outra versão: suba a stack com `SUPERSET_VERSION=<versão>` e `SUPERSET_LOAD_EXAMPLES=1` e rode o
script com `SUPERSET_URL`, `SUPERSET_USERNAME` e `SUPERSET_PASSWORD`.
