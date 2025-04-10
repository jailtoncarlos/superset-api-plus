from dataclasses import dataclass

from supersetapiplus.base.base import Object
from supersetapiplus.base.types import DatasourceType


@dataclass
class DataSource(Object):
    id: int = None
    type: DatasourceType = DatasourceType.TABLE