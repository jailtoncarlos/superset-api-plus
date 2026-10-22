"""Extrai do código-fonte do Superset os enums e `choices` usados nos testes de conformidade de enums.

A especificação OpenAPI tipa muitos campos só como `string`; os valores aceitos estão no fonte
(enums do backend e do frontend, e `choices` dos controlPanels). Este script baixa os arquivos da
versão indicada e gera o recorte versionado em tests/fixtures.

Uso:
    python bin/scripts/extrair_enums_superset.py 6.1.0 > tests/fixtures/superset_enums_6.1.0.json
"""
import ast
import json
import re
import sys
import urllib.request

RAIZ = "https://raw.githubusercontent.com/apache/superset/{versao}/{caminho}"

# Enums Python do backend: (arquivo, classe).
BACKEND = [
    ("superset/utils/core.py", "FilterOperator"),
    ("superset/common/chart_data.py", "ChartDataResultFormat"),
    ("superset/common/chart_data.py", "ChartDataResultType"),
    ("superset/constants.py", "TimeGrain"),
]

# Enums TypeScript do frontend: (arquivo, enum).
FRONTEND = [
    ("superset-frontend/src/explore/constants.ts", "Operators"),
]

# `choices` de controles do controlPanel: (chave, arquivo, nome do controle).
CHOICES = [
    ("pivot_table_v2.aggregateFunction",
     "superset-frontend/plugins/plugin-chart-pivot-table/src/plugin/controlPanel.tsx", "aggregateFunction"),
]


def baixar(versao: str, caminho: str) -> str:
    with urllib.request.urlopen(RAIZ.format(versao=versao, caminho=caminho), timeout=60) as resposta:
        return resposta.read().decode("utf-8")


def enum_python(fonte: str, classe: str) -> dict[str, str]:
    for no in ast.walk(ast.parse(fonte)):
        if isinstance(no, ast.ClassDef) and no.name == classe:
            return {
                alvo.id: item.value.value
                for item in no.body if isinstance(item, ast.Assign) and isinstance(item.value, ast.Constant)
                for alvo in item.targets if isinstance(alvo, ast.Name)
            }
    raise ValueError(f"classe {classe} não encontrada")


def enum_typescript(fonte: str, nome: str) -> dict[str, str]:
    corpo = re.search(rf"export enum {nome} \{{(.*?)\}}", fonte, re.S)
    if not corpo:
        raise ValueError(f"enum {nome} não encontrado")
    return dict(re.findall(r"(\w+)\s*=\s*'([^']*)'", corpo.group(1)))


def choices_do_controle(fonte: str, controle: str) -> list[str]:
    bloco = re.search(rf"name:\s*'{controle}'.*?choices:\s*\[(.*?)\n\s*\],", fonte, re.S)
    if not bloco:
        raise ValueError(f"choices de {controle} não encontrados")
    return re.findall(r"\[\s*'([^']+)'\s*,", bloco.group(1))


def main(versao: str) -> None:
    cache: dict[str, str] = {}

    def fonte(caminho: str) -> str:
        if caminho not in cache:
            cache[caminho] = baixar(versao, caminho)
        return cache[caminho]

    recorte = {
        "superset_version": versao,
        "backend": {classe: enum_python(fonte(arquivo), classe) for arquivo, classe in BACKEND},
        "frontend": {nome: enum_typescript(fonte(arquivo), nome) for arquivo, nome in FRONTEND},
        "choices": {chave: choices_do_controle(fonte(arquivo), controle) for chave, arquivo, controle in CHOICES},
    }
    json.dump(recorte, sys.stdout, ensure_ascii=False, indent=1, sort_keys=True)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main(sys.argv[1])
