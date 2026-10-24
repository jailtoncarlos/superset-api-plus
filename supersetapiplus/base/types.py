from supersetapiplus.base.enum_str import StringEnum


class DatasourceType(StringEnum):
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
