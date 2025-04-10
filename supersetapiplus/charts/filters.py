import json
from dataclasses import dataclass, field

from supersetapiplus.base.base import Object, default_string
from supersetapiplus.charts.types import FilterOperatorType, FilterExpressionType, FilterClausesType
from supersetapiplus.typing import Optional


#https://github.com/apache/superset/blob/8553b06155249c3583cf0dcd22221ec06cbb833d/superset/utils/core.py#L137


@dataclass
class AdhocFilterClause(Object):
    expressionType: FilterExpressionType = FilterExpressionType.SIMPLE
    subject: str = None
    operator: FilterOperatorType = None
    comparator: str = None
    clause: str = FilterClausesType.WHERE
    sqlExpression: str = None
    operatorId: Optional[str] = None

    isExtra: bool = False
    isNew: bool = False

