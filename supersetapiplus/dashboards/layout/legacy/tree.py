
from anytree import PreOrderIter, RenderTree, search
from typing_extensions import Self

from supersetapiplus.dashboards.layout.legacy.items import GridItemPosition, ItemPosition, ItemPositionType, RootItemPosition
from supersetapiplus.dashboards.layout.legacy.nodes import GridNodePosition, NodePosition, NodePositionParse, RootNodePosition


class TreeNodePosition:
    def __init__(self):
        self._root = RootNodePosition(RootItemPosition())
        GridNodePosition(GridItemPosition(), self._root)

    @property
    def root(self) -> NodePosition:
        return self._root

    @property
    def grid(self) -> NodePosition:
        return self.find_by_id('GRID_ID')

    def insert(self, item: ItemPosition, parent: Self) -> NodePosition:
        return NodePositionParse.get_instance(item, item.type_, parent)

    def chart_ids(self) -> list[int]:
        """Ids of the charts present in the layout, in tree order."""
        return [node.item.chart_id for node in PreOrderIter(self._root) if node.type_ == ItemPositionType.CHART]

    def find_by_id(self, id: str):
        node = search.find(self._root, lambda node: node.name == id)
        return node

    def print(self):
        for pre, _fill, node in RenderTree(self.root):
            print(f"{pre}{node.item}")  # noqa: T201 - public method whose purpose is to print the tree

    def __to_dict(self, node: NodePosition, values: dict):
        for child_id in node.item.children:
            node_child = self.find_by_id(child_id)
            values[child_id] = node_child.item.to_dict()
            self.__to_dict(node_child, values)

    def to_dict(self) -> dict:
        values = {}
        values[self.root.id] = self.root.item.to_dict()
        self.__to_dict(self.root, values)
        return values

    @classmethod
    def __generate_tree(cls, position_id: str, data: dict, tree: Self):
        parent_node = tree.find_by_id(position_id)
        if position_id in data:
            parent_node_value = data[position_id]
            for child_position_id in parent_node_value.get("children", []):
                position_node = tree.find_by_id(child_position_id)
                if not position_node:
                    kwargs = data[child_position_id].copy()
                    kwargs.pop('children')
                    kwargs.pop('parents')
                    metadata = data[child_position_id].get('meta', {})
                    if metadata:
                        kwargs.update(metadata)
                    item_position = ItemPosition.get_instance(**kwargs)
                    tree.insert(item_position, parent_node)
                cls.__generate_tree(child_position_id, data, tree)

    @classmethod
    def from_dict(cls, data: dict):
        tree = cls()
        tree.root.item.parents = data['ROOT_ID'].get('parents', [])
        tree.root.item.children = data['ROOT_ID']['children']

        grid_node = tree.find_by_id('GRID_ID')
        grid_node.item.parents = data['GRID_ID']['parents']

        cls.__generate_tree('ROOT_ID', data, tree)
        return tree
