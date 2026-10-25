
from pydantic import Field

from supersetapiplus.core.api_model import ApiModel
from supersetapiplus.core.types import DatasourceType


class DataSource(ApiModel):
    """Reference to a Superset datasource (its id and type, e.g. a dataset is `table`), as charts point to it."""
    id: int | None = None
    type: DatasourceType = Field(default_factory=lambda: DatasourceType.TABLE)
