# Referências de gráficos salvos pelo Superset 6.1.0

Um JSON por `viz_type` com o `result` do `GET /api/v1/chart/{id}` de gráficos dos **exemplos
públicos do Apache Superset** (databases e datasets de exemplo: `birth_names`, `covid_vaccines`,
`cleaned_sales_data`, `users`). Não contêm dados de nenhuma instituição. `INDICE.json` lista id,
título, dataset e se o `query_context` (gerado pelo frontend) está presente.

Usados por `tests/unit/test_referencias_ui.py`: leitura e regravação sem perda e, onde há
`query_context`, comparação do que a biblioteca gera com o que a UI gerou. `cal_heatmap` não existe
nos exemplos.
