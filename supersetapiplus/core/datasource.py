from dataclasses import dataclass, field

from supersetapiplus.core.model import SerializableModel
from supersetapiplus.core.types import DatasourceType


@dataclass
class DataSource(SerializableModel):
    id: int | None = field(default=None)
    type: DatasourceType = field(default_factory=lambda: DatasourceType.TABLE)
