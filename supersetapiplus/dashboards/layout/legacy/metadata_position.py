from pydantic import PrivateAttr

from supersetapiplus.core.api_model import ApiModel
from supersetapiplus.dashboards.layout.legacy.items import (
    ChartItemPosition,
    ColumnItemPosition,
    ItemPosition,
    MarkdownItemPosition,
    TabItemPosition,
)
from supersetapiplus.dashboards.layout.legacy.nodes import (
    ChartNodePosition,
    MarkdownNodePosition,
    NodePosition,
    TabNodePosition,
)
from supersetapiplus.dashboards.layout.legacy.tree import TreeNodePosition
from supersetapiplus.deprecation import module_aliases


class MetadataPosition(ApiModel):
    DASHBOARD_VERSION_KEY: str = 'v2'
    _tree: TreeNodePosition = PrivateAttr(default_factory=TreeNodePosition)

    def __init__(self, tree: TreeNodePosition = None, **kwargs):
        super().__init__(**kwargs)
        if tree is not None:
            self._tree = tree

    @property
    def tree(self):
        return self._tree

    def to_dict(self, columns: list = None, convert_to_json: bool = False) -> dict:
        data = super().to_dict(columns, convert_to_json)
        data.update(self.tree.to_dict())
        return data

    @classmethod
    def from_json(cls, data: dict):
        maindata = {}
        for k, v in data.items():
            if not isinstance(v, dict):
                maindata[k] = v
        obj = super().from_json(maindata)
        obj._tree = TreeNodePosition.from_dict(data)
        return obj

    def add(self, item: ItemPosition, parent: ItemPosition) -> NodePosition:
        return self.tree.insert(item, parent)

    def add_tab(self, title: str, parent: ItemPosition = None) -> TabNodePosition:
        if not parent:
            parent = self.tree.grid
        return self.tree.insert(TabItemPosition(text=title), parent)

    def add_column(self, parent: ItemPosition = None, width: int = 4, background: str = 'BACKGROUND_TRANSPARENT',
                   relocate: bool = True) -> MarkdownNodePosition:
        if not parent:
            parent = self.tree.grid
        return self.tree.insert(ColumnItemPosition(width=width, background=background, relocate=relocate), parent)

    def add_markdown(self, markdown: str, parent: ItemPosition = None, height: int = 50, width: int = 4,
                     relocate: bool = True) -> MarkdownNodePosition:
        if not parent:
            parent = self.tree.grid
        return self.tree.insert(MarkdownItemPosition(code=markdown, height=height, width=width, relocate=relocate), parent)

    def add_chart(self, chart, title: str, parent: ItemPosition = None, height: int = 50, width: int = 4,
                  relocate: bool = True) -> ChartNodePosition:
        if not parent:
            parent = self.tree.grid
        return self.tree.insert(ChartItemPosition(chartId=chart.id,
                                                  sliceName=chart.slice_name,
                                                  sliceNameOverride=title,
                                                  height=height,
                                                  width=width,
                                                  relocate=relocate), parent)


# Old names, kept as aliases that emit DeprecationWarning.
__getattr__ = module_aliases(__name__, globals(), {"Metadataposition": "MetadataPosition"})
