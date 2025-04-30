from dataclasses import dataclass, field

from supersetapiplus.base.base import Object
from supersetapiplus.base.types import DatasourceType


@dataclass
class DataSource(Object):
    id: int = None
    type: DatasourceType = field(default_factory=lambda: DatasourceType.TABLE)