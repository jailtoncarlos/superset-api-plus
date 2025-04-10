# CHANGELOG

## 1.0.0a1 (2025-04-10)

### Refatoração e Melhorias de Empacotamento

* **Refatoração da Estrutura de Empacotamento e Qualidade:**
    * Substituição da estrutura baseada em `setup.py`/`setup.cfg` por `pyproject.toml`.
    * Adição de `CHANGELOG.md` para rastrear o histórico de versões.
    * Remoção de arquivos legados: `setup.py`, `setup.cfg`, `requirements.txt`, `pytest.ini`.
    * Remoção de scripts locais de lint (`bin/`) e arquivo `.pylintrc`.
    * Atualização de `.pre-commit-config.yaml` com ferramentas modernas: `ruff`, `mypy`, `codespell`.
    * Remoção de `black`, `isort` e `pylint` do pre-commit (substituídos por `ruff`).
    * Migração da configuração do `pytest.ini` para `[tool.pytest.ini_options]` no `pyproject.toml`.
    * Adição das regras `T201` (print) e `T100` (pdb) no `ruff` para detectar comandos indevidos.
    * Simplificação da estrutura para seguir boas práticas modernas de bibliotecas Python.

* **Remoção da Pasta `requirements` e Migração de Extras para `pyproject.toml`:**
    * Remoção dos arquivos `requirements-dev.txt`, `requirements-testing.txt` e `requirements-packaging.txt`.
    * Definição das seções `[project.optional-dependencies]` com os extras "dev" e "test".
    * Permissão de instalação via `pip install .[dev,test]`.
    * Eliminação de redundância e centralização da configuração no `pyproject.toml`.

* **Preparação da Versão 1.0.0a1:**
    * Adição de `pyproject.toml` com metadados do projeto e ferramentas de linting (`black`, `isort`, `mypy`, `ruff`).
    * Atualização da versão do projeto para `1.0.0a1` (alpha release pública).
    * Adição do changelog inicial com o registro da refatoração e funcionalidades principais.

* **Renomeação e Reestruturação do Projeto:**
    * Renomeação do projeto de `superset-api-client` para `superset-api-plus`.
    * Definição do nome do pacote Python como `supersetapiclientplus`.
    * Atualização de todos os imports no código-fonte, exemplos e testes.
    * Substituição de ferramentas antigas no pre-commit por `ruff`, `black`, `mypy`, `isort` e `codespell`.
    * Adição de arquivos essenciais para empacotamento e publicação: `setup.py`, `setup.cfg`, `MANIFEST.in`, `.pylintrc`, `.pypirc`.
    * Organização dos requirements por ambiente (dev, packaging, testing).
    * Atualização dos metadados do projeto (autor, e-mail, keywords, versão).
    * Remoção de dependências não utilizadas no `requirements-packaging`.
    * Preparação da biblioteca para publicação no PyPI (versão 0.5.0).

* **Criação do README.md:**
    * Adicionado o arquivo `README.md`.

* **Remoção do arquivo `MANIFEST.in`:**
    * Arquivo removido por não ser mais necessário no novo empacotamento.