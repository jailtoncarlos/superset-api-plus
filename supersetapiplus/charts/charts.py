"""Charts."""
import copy
import logging
from abc import abstractmethod
from dataclasses import dataclass, field

from typing_extensions import Self

from supersetapiplus.base.base import ApiModelFactories, SerializableModel
from supersetapiplus.base.fields import object_field
from supersetapiplus.base.types import DatasourceType
from supersetapiplus.charts.metric import OrderBy
from supersetapiplus.charts.options import Option
from supersetapiplus.charts.queries import AdhocMetricColumn
from supersetapiplus.charts.query_context import DataSource, QueryContext
from supersetapiplus.charts.types import ChartType, FilterClausesType, FilterExpressionType, FilterOperatorType, MetricType
from supersetapiplus.dashboards.dashboards import Dashboard
from supersetapiplus.exceptions import ChartValidationError, DashboardValidationError, NotFound, ValidationError
from supersetapiplus.typing import SerializableNotToJson, SerializableOptional
from supersetapiplus.utils.dict_utils import detailed_dict_diff

logger = logging.getLogger(__name__)


@dataclass
class Chart(SerializableModel):
    JSON_FIELDS = ['params', 'query_context']
    PRESERVE_EXTRA_FIELDS = False
    # Campos aceitos pela API (OpenAPI 6.1.0: ChartRestApi.post / ChartRestApi.put).
    POST_FIELDS = (
        "cache_timeout", "certification_details", "certified_by", "dashboards", "datasource_id",
        "datasource_name", "datasource_type", "description", "external_url", "is_managed_externally",
        "owners", "params", "query_context", "query_context_generation", "slice_name", "viz_type",
    )
    PUT_FIELDS = (
        "cache_timeout", "certification_details", "certified_by", "dashboards", "datasource_id",
        "datasource_type", "description", "external_url", "is_managed_externally", "owners", "params",
        "query_context", "query_context_generation", "slice_name", "tags", "viz_type",
    )
    # Campos que o Superset legitimamente mantém diferentes entre params e
    # query_context.form_data: identidade (slice_id antigo após import/export de dashboards)
    # e parâmetros de requisição que o frontend injeta apenas no form_data.
    VOLATILE_FORM_DATA_FIELDS = {'slice_id', 'dashboards', 'force', 'result_format', 'result_type'}
    # Sufixos de chaves que o Superset grava em params mas pode omitir de query_context.form_data
    # (ex.: chaves da query B do mixed_timeseries). Só a ausência é tolerada, não valores divergentes.
    PARAMS_ONLY_FIELD_SUFFIXES = ()

    slice_name: str
    id: int = field(default=None)
    description: str = field(default=None)
    viz_type: ChartType = field(default=None)

    certification_details: str = field(default=None)
    certified_by: str = field(default=None)
    is_managed_externally: bool = field(default=None)

    params: Option = field(init=False)  # Não instanciar Option diretamente!
    query_context: QueryContext = object_field(cls=QueryContext, default_factory=QueryContext)

    datasource_id: SerializableOptional[int] = field(default=None)
    datasource_type: SerializableOptional[DatasourceType] = field(default=None)
    cache_timeout: int = field(default=None)

    dashboards: SerializableNotToJson[list[Dashboard]] = object_field(cls=Dashboard, default_factory=list)
    owners: SerializableNotToJson[list[dict]] = field(default=None)

    tags: SerializableNotToJson[list] = field(default=None)

    changed_on_delta_humanized: SerializableNotToJson[str] = None
    _slice_name_override: SerializableNotToJson[str] = field(default=None)
    thumbnail_url: SerializableNotToJson[str] = field(default=None)
    url: SerializableNotToJson[str] = field(default=None)


    @classmethod
    @abstractmethod
    def _default_option_class(cls) -> type[Option]:
        ...

    def __post_init__(self):
        super().__post_init__()
        from supersetapiplus.dashboards.dashboards import Dashboard
        self._dashboards = [Dashboard(dashboard_title='')]

        if not hasattr(self, "params") or self.params is None:
            self.params = self._default_option_class()()  # Assume que existe esse método na subclasse concreta

        if self.id is None:
            if self.datasource_id is None:
                raise ChartValidationError("""
                    When id is None, argument datasource id becomes mandatory.
                    We recommend using the [client_superset].datasets.get_id_by_name('name_dataset') method
                    to get the dataset id by name.
                """)

            self._preencher_datasource()

    def _preencher_datasource(self):
        """Gráfico novo: params (e query_context) recebem o datasource de datasource_id/datasource_type.

        Chamado no __post_init__ e, de novo, no fim de from_json: durante o from_json o __post_init__
        roda com params ainda como dict (a conversão para Option vem depois).
        """
        if self.id is not None or self.datasource_id is None or not isinstance(self.params, SerializableModel):
            return
        if not self.params.datasource:  # None ou MissingField (ausente no JSON)
            self.params.datasource = f'{self.datasource_id}__{self.datasource_type}'
            if isinstance(self.query_context, SerializableModel):
                self.query_context.datasource.id = self.datasource_id
                self.query_context.form_data = copy.deepcopy(self.params)

    def validate(self):
        super().validate()
        # query_context nulo (chart nunca salvo pelo Explore) ou sem form_data (charts de exemplo
        # carregados por YAML no Superset 6.1) não têm o que comparar com params.
        if self.query_context is None or not isinstance(self.query_context.form_data, SerializableModel):
            return

        params = {k: v for k, v in self.params.to_dict().items() if k not in self.VOLATILE_FORM_DATA_FIELDS}
        form_data = {k: v for k, v in self.query_context.form_data.to_dict().items()
                     if k not in self.VOLATILE_FORM_DATA_FIELDS}
        # Versões antigas do Superset gravavam form_data.datasource como "None__table";
        # o params continua sendo a fonte da verdade e o Superset ignora o valor inválido.
        if str(form_data.get('datasource', '')).startswith('None__'):
            form_data['datasource'] = params.get('datasource')
        if self.PARAMS_ONLY_FIELD_SUFFIXES:
            params = {k: v for k, v in params.items()
                      if k in form_data or not k.endswith(self.PARAMS_ONLY_FIELD_SUFFIXES)}
        if params != form_data:
            added, removed, modified, same = detailed_dict_diff(params, form_data)

            raise ValidationError(message=f'self.params is not the same as self.query_conext.form_data. '
                                          f'Diff: modified={modified}, added={added}, removed={removed}',
                                  solution="We recommend using the public methods of the chart class.")

    @classmethod
    def instance(cls,
                 slice_name: str,
                 datasource: DataSource,
                 options: Option = None):

        if options is None:
            options = cls._default_option_class()()  # delega para a subclasse

        new_chart = cls(slice_name=slice_name,
                        datasource_id=datasource.id,
                        datasource_type=datasource.type)

        options.datasource = f'{datasource.id}__{datasource.type}'

        new_chart.params = options
        new_chart.query_context.form_data = copy.deepcopy(options)
        return new_chart

    def add_dashboard(self, dashboard):
        self.dashboards.append(dashboard)
        self.query_context.add_dashboard(dashboard.id)

    def clone(self, slice_name: str = None, slice_name_override: str = None, clear_dashboard: bool = False,
              clear_filter: bool = True) -> Self:
        new_chart = copy.deepcopy(self)
        new_chart.slice_name = slice_name or f'{new_chart.slice_name}_clone'
        new_chart._slice_name_override = slice_name_override or f'Chart clone de {new_chart.slice_name}'
        new_chart.id = 0

        if clear_dashboard:
            new_chart.dashboards = []
        if clear_filter:
            new_chart.clear_filter()

        return new_chart

    def clear_filter(self) -> None:
        self.params.adhoc_filters = []
        for query in self.query_context.queries:
            query.filters = []
        self.query_context.form_data.adhoc_filters = []

    def add_simple_metric(self, metric: MetricType, automatic_order: OrderBy = OrderBy()):
        self.params._add_simple_metric(metric, automatic_order)
        self.query_context._add_simple_metric(metric, automatic_order)

    def add_custom_metric(self, label: str,
                          automatic_order: OrderBy = OrderBy(),
                          column: AdhocMetricColumn = None,
                          sql_expression: str = None,
                          aggregate: MetricType = None):
        if column:
            column.id = self.id
        self.params._add_custom_metric(label, automatic_order, column, sql_expression, aggregate)
        self.query_context._add_custom_metric(label, automatic_order, column, sql_expression, aggregate)

    def add_simple_orderby(self, column_name: str,
                            sort_ascending: bool = True):
        self.query_context._add_simple_orderby(column_name, sort_ascending)

    def add_custom_orderby(self, label: str,
                             sort_ascending: bool,
                             column: AdhocMetricColumn = None,
                             sql_expression: str = None,
                             aggregate: MetricType = None):
        self.query_context._add_custom_orderby(label, sort_ascending, column, sql_expression, aggregate)

    def add_simple_dimension(self, column_name: str):
        self.params._add_simple_groupby(column_name)
        self.query_context._add_simple_groupby(column_name)

    def add_custom_dimension(self, label: str,
                             column: AdhocMetricColumn = None,
                             sql_expression: str = None,
                             aggregate: MetricType = None):
        self.params._add_custom_groupby(label, column, sql_expression, aggregate)
        self.query_context._add_custom_groupby(label, column, sql_expression, aggregate)

    def add_simple_filter(self, column_name: str,
                          value: str,
                          operator: FilterOperatorType = FilterOperatorType.EQUALS) -> None:
        self.params._adhoc_filters(expression_type=FilterExpressionType.SIMPLE,
                                   clause=FilterClausesType.WHERE,
                                   subject=column_name,
                                   comparator=value,
                                   operator=operator)
        self.query_context._add_simple_filter(column_name=column_name,
                                              value=value,
                                              operator=operator)

    def add_extra_where(self, sql: str):
        self.params._adhoc_filters(expression_type=FilterExpressionType.CUSTOM_SQL,
                                   clause=FilterClausesType.WHERE,
                                   sql_expression=sql)
        self.query_context._add_extra_where(sql)

    def add_extra_having(self, sql: str):
        self.query_context._add_extra_having(sql)

    def to_json(self, columns: list = None) -> dict:
        data = super().to_json(columns).copy()
        return data

    @classmethod
    def from_json(cls, data: dict):
        obj = super().from_json(data)
        obj._dashboards = obj.dashboards

        # O Superset mantém query_context nulo em charts que nunca foram salvos pelo Explore
        # (comum em charts importados). Preserva o nulo em vez de fabricar um contexto vazio.
        if data.get('query_context') in (None, '', 'null'):
            obj.query_context = None

        # Datasource: o GET /chart/{id} traz datasource_id/datasource_type no topo, que prevalecem;
        # params.datasource pode estar desatualizado (ex.: charts de exemplo importados).
        if data.get('datasource_id'):
            obj.datasource_id = int(data['datasource_id'])
            obj.datasource_type = DatasourceType(data.get('datasource_type') or 'table')
        elif obj.query_context:
            datasource = obj.query_context.datasource
            if datasource and datasource.id:
                obj.datasource_id = datasource.id
                obj.datasource_type = datasource.type
            else:
                logger.warning("datasource query_context without 'id' defined")
        elif isinstance(obj.params, SerializableModel) and '__' in str(obj.params.datasource or ''):
            # Listagens com colunas restritas (find(columns=[...])) não trazem params: o objeto
            # parcial fica sem datasource e é completado por find_one(..., full=True).
            datasource_id, datasource_type = str(obj.params.datasource).split('__', 1)
            obj.datasource_id = int(datasource_id)
            obj.datasource_type = DatasourceType(datasource_type)

        obj._preencher_datasource()
        return obj


class Charts(ApiModelFactories):
    endpoint = "chart/"

    def _default_object_class(self) -> type[SerializableModel]:
        return Chart

    def get_chart_data(self, slice_id: int, dashboard_id: int | None = None) -> list[dict]:
        """
        Dados do gráfico calculados pelo Superset com o query_context salvo (GET /chart/{pk}/data/).

        Args:
            slice_id: id do gráfico.
            dashboard_id: se informado, confere que o gráfico pertence a esse dashboard.

        Returns:
            list[dict]: um item por consulta do query_context (`data`, `colnames`, `rowcount`...).
        """
        if dashboard_id is not None and dashboard_id not in self.dashboard_ids(slice_id):
            raise NotFound(f'Chart {slice_id} does not belong to dashboard {dashboard_id}.')
        url = self.client.join_urls(self.base_url, slice_id, "data/")
        return self.client.get(url, params={"format": "json", "type": "full"}).json()["result"]

    def dashboard_ids(self, chart_id: int) -> list[int]:
        """Ids dos dashboards associados ao gráfico, como o Superset os tem gravados."""
        result = self.client.get(self.client.join_urls(self.base_url, chart_id)).json()["result"]
        return [d["id"] for d in result.get("dashboards") or []]

    def add_to_dashboard(self, chart: Chart | int, dashboard_id: int) -> list[int]:
        """
        Associa o gráfico ao dashboard (PUT /chart/{pk} só com `dashboards`), mantendo as associações existentes.

        A associação é por id no gráfico: o campo `dashboards` do ChartPutSchema substitui a lista,
        por isso as atuais são lidas antes. Devolve a lista gravada.
        """
        chart_id = chart if isinstance(chart, int) else chart.id
        if not chart_id:
            raise ChartValidationError('Save the chart before attaching it to a dashboard (chart.id is empty).')
        atuais = self.dashboard_ids(chart_id)
        if dashboard_id in atuais:
            return atuais
        novos = atuais + [dashboard_id]
        self.client.put(self.client.join_urls(self.base_url, chart_id), json={"dashboards": novos})
        return novos

    def add_and_attach_to_dashboard(self, chart: Chart, title: str, parent=None) -> int:
        """
        Cria o gráfico e o coloca no layout do dashboard ao qual o gráfico de origem pertence.

        Args:
            chart (Chart): gráfico a criar (ex.: clone de um gráfico já associado a um dashboard).
            title (str): título exibido no dashboard (sliceNameOverride).
            parent (NodePosition, opcional): nó do layout onde inserir.

        Returns:
            int: id do gráfico criado.

        Raises:
            DashboardValidationError: o gráfico de origem não pertence a nenhum dashboard.
        """
        # Valida antes de criar: antes, o gráfico era criado e ficava órfão quando a validação falhava.
        if not chart.dashboards:
            raise DashboardValidationError(
                message="Não foi possível anexar o chart: ele não pertence a nenhum dashboard.",
                solution="Verificar se o chart informado está associado a um dashboard antes de chamar este método."
            )
        dashboard = self.client.dashboards.get(chart.dashboards[0].id)
        new_id = self.add(chart)
        dashboard.add_chart(chart, title, parent)
        dashboard.save()
        return new_id
