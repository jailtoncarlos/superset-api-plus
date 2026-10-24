from dataclasses import dataclass, field

from supersetapiplus.base.types import DatasourceType
from supersetapiplus.core.model import SerializableModel


@dataclass
class DataSource(SerializableModel):
    id: int | None = field(default=None)
    type: DatasourceType = field(default_factory=lambda: DatasourceType.TABLE)
