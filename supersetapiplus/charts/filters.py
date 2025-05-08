from dataclasses import dataclass, field

from supersetapiplus.base.base import SerializableModel
from supersetapiplus.charts.types import FilterOperatorType, FilterExpressionType, FilterClausesType
from supersetapiplus.typing import SerializableOptional


#https://github.com/apache/superset/blob/8553b06155249c3583cf0dcd22221ec06cbb833d/superset/utils/core.py#L137


@dataclass
class AdhocFilterClause(SerializableModel):
    expressionType: FilterExpressionType = field(default_factory=lambda: FilterExpressionType.SIMPLE)
    subject: str = field(default=None)
    operator: FilterOperatorType = field(default=None)
    comparator: str = field(default=None)
    clause: FilterClausesType = field(default_factory=lambda: FilterClausesType.WHERE)
    sqlExpression: SerializableOptional[str] = field(default=None)
    operatorId: SerializableOptional[str] = field(default=None)

    isExtra: SerializableOptional[bool] = field(default=None)
    isNew: SerializableOptional[bool] = field(default=None)

    datasourceWarning: SerializableOptional[bool] = field(default=None)
    filterOptionName: SerializableOptional[str] = field(default=None)
