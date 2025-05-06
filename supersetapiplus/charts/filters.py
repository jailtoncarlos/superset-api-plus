from dataclasses import dataclass, field

from supersetapiplus.base.base import SerializableModel
from supersetapiplus.charts.types import FilterOperatorType, FilterExpressionType, FilterClausesType
from supersetapiplus.typing import SerializableOptional


#https://github.com/apache/superset/blob/8553b06155249c3583cf0dcd22221ec06cbb833d/superset/utils/core.py#L137


@dataclass
class AdhocFilterClause(SerializableModel):
    expressionType: FilterExpressionType = field(default_factory=lambda: FilterExpressionType.SIMPLE)
    subject: str = None
    operator: FilterOperatorType = None
    comparator: str = None
    clause: FilterClausesType = field(default_factory=lambda: FilterClausesType.WHERE)
    sqlExpression: str = None
    operatorId: SerializableOptional[str] = None

    isExtra: bool = False
    isNew: bool = False

    datasourceWarning: bool = False
    filterOptionName: SerializableOptional[str] = None
