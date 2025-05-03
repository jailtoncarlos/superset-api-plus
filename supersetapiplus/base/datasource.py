from dataclasses import dataclass, field

from supersetapiplus.base.base import SerializableModel
from supersetapiplus.base.types import DatasourceType


@dataclass
class DataSource(SerializableModel):
    id: int = None
    type: DatasourceType = field(default_factory=lambda: DatasourceType.TABLE)