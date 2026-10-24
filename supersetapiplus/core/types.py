from enum import IntEnum

from supersetapiplus.core.enums import StringEnum


class DatasourceType(StringEnum):
    """Type of a datasource (`superset/utils/core.py` DatasourceType and the frontend one, Superset 6.1.0)."""
    SLTABLE = "sl_table"
    TABLE = "table"
    DATASET = "dataset"
    QUERY = "query"
    SAVEDQUERY = "saved_query"
    VIEW = "view"


class DatasourceKind(StringEnum):
    """Dataset kind (`superset/connectors/sqla/models.py` DatasourceKind, Superset 6.1.0)."""
    VIRTUAL = "virtual"
    PHYSICAL = "physical"


class ConfigurationMethod(StringEnum):
    """How a database connection was configured (`superset/models/core.py` ConfigurationMethod, 6.1.0)."""
    SQLALCHEMY_FORM = "sqlalchemy_form"
    DYNAMIC_FORM = "dynamic_form"


class LimitingFactor(StringEnum):
    """What limited a SQL Lab result (`superset/sqllab/limiting_factor.py`, Superset 6.1.0)."""
    QUERY = "QUERY"
    DROPDOWN = "DROPDOWN"
    QUERY_AND_DROPDOWN = "QUERY_AND_DROPDOWN"
    NOT_LIMITED = "NOT_LIMITED"
    UNKNOWN = "UNKNOWN"


class GenericDataType(IntEnum):
    """Generic type of a column (`superset/utils/core.py` GenericDataType, Superset 6.1.0): `type_generic` of
    dataset columns and of query results."""
    NUMERIC = 0
    STRING = 1
    TEMPORAL = 2
    BOOLEAN = 3
    # ARRAY = 4     # Mapping all the complex data types to STRING for now
    # JSON = 5      # and leaving these as a reminder.
    # MAP = 6
    # ROW = 7
