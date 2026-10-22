"""Extrai da especificação OpenAPI oficial do Superset o recorte usado nos testes de conformidade.

Uso (baixa a especificação oficial da versão no repositório do Superset):
    python bin/scripts/extrair_openapi.py <versão> > tests/fixtures/superset_openapi_<versão>.json
ou, com um arquivo já baixado:
    python bin/scripts/extrair_openapi.py <versão> /caminho/openapi.json > ...

Mantém todas as rotas (só os métodos) e os schemas de criação/alteração dos recursos que a
biblioteca grava, com propriedades, tipos e campos obrigatórios.
"""
import json
import sys
import urllib.request

URL_SPEC = "https://raw.githubusercontent.com/apache/superset/{versao}/docs/static/resources/openapi.json"

RECURSOS = ["ChartRestApi", "DashboardRestApi", "DatasetRestApi", "DatabaseRestApi", "SavedQueryRestApi"]


def recorte_schema(schema: dict) -> dict:
    propriedades = {
        nome: {k: v for k, v in prop.items() if k in ("type", "nullable", "enum", "maxLength")}
        for nome, prop in schema.get("properties", {}).items()
    }
    return {"properties": propriedades, "required": sorted(schema.get("required", []))}


def carregar_spec(versao: str, caminho: str | None) -> dict:
    if caminho:
        with open(caminho, encoding="utf-8") as arquivo:
            return json.load(arquivo)
    with urllib.request.urlopen(URL_SPEC.format(versao=versao), timeout=120) as resposta:
        return json.load(resposta)


def main(versao: str, caminho: str | None = None) -> None:
    spec = carregar_spec(versao, caminho)
    schemas = spec["components"]["schemas"]
    recorte = {
        "superset_version": versao,
        "paths": {path: sorted(m for m in ops if m in ("get", "post", "put", "delete"))
                  for path, ops in sorted(spec["paths"].items())},
        "schemas": {f"{r}.{op}": recorte_schema(schemas[f"{r}.{op}"])
                    for r in RECURSOS for op in ("post", "put") if f"{r}.{op}" in schemas},
    }
    json.dump(recorte, sys.stdout, ensure_ascii=False, indent=1, sort_keys=True)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main(*sys.argv[1:3])  # versão [arquivo]
