from dataclasses import dataclass, field

from supersetapiplus.core.model import SerializableModel
from supersetapiplus.core.types import DatasourceType


@dataclass
class DataSource(SerializableModel):
    """Reference to a Superset datasource (its id and type, e.g. a dataset is `table`), as charts point to it."""
    id: int | None = field(default=None)
    type: DatasourceType = field(default_factory=lambda: DatasourceType.TABLE)
