import logging
from abc import ABC, abstractmethod

from anytree import Node
from typing_extensions import Self

from supersetapiplus.base.parse import ParseMixin
from supersetapiplus.dashboards.itemposition import (
    ColumnItemPosition,
    ItemPosition,
    ItemPositionType,
    MarkdownItemPosition,
    RowItemPosition,
    TabItemPosition,
    TabsItemPosition,
)
from supersetapiplus.exceptions import AcceptChildError, NodePositionValidationError

logger = logging.getLogger(__name__)


def _not_enough_space(total_width: int) -> NodePositionValidationError:
    return NodePositionValidationError(
        f'There is not enough space for this component. Total {total_width} exceeds the maximum allowable width '
        f'of {ItemPosition.MAX_WIDTH}.')


class NodePosition(Node, ParseMixin, ABC):
    def __init__(self, item: ItemPosition, parent: Self=None):
        super().__init__(item.id, parent)
        self._is_sibling_left = False
        self._is_sibling_right = False

        self._item = item
        self._validate(item)
        if parent and not parent.item.ACCEPT_CHILD:
            raise AcceptChildError()
        self._add_child(parent)

    @abstractmethod
    def _validate(self, item: ItemPosition):
        return

    def _add_child(self,  parent: Self):
        if parent:
            parent.item.children.append(self.item.id)
            self.item.parents = [p.item.id for p in self.path][:-1]

    @property
    def item(self):
        return self._item

    @property
    def id(self):
        return self._item.id

    @property
    def type_(self):
        return ItemPositionType(self.item.type_)

    def get_new_node_position(self, item: ItemPosition, parent: Self):
        return NodePositionParse.get_instance(item, item.type_, parent)

    def insert(self, item: ItemPosition) -> Self:
        if not item.ACCEPT_CHILD:
            raise NodePositionValidationError(f'{self.get_class(item.type_).__name__} component does not allow children')
        return NodePositionParse.get_instance(item, item.type_, self)

    def _insert_parent(self, item: ItemPosition, parent: Self, NodePositionClass:Self):
        if parent.type_ != item.type_:
            return NodePositionClass(item, parent)
        return parent

    def _get_or_insert_parent(self, item: ItemPosition, parent: Self, NodePositionClass: Self):
        '''
        Checks if the parent node is of type item.type_, if yes, return it,
        If the parent is not of type item.type_, check if there is a child of type TABS, if so, return the first one.
        If the parent is not of type item.type_ and there are no children of type item.type_, add a new node to the tree
        and return it as the parent.
        :param item: GenericItemPosition
        :param parent: NodePosition
        :return: new NodePosition or parent
        '''
        if parent.type_ != item.type_:
            child_tabs_exists = False
            for child in parent.children:
                if child.type_ == item.type_:
                    parent = child
                    child_tabs_exists = True
            if not child_tabs_exists:
                return NodePositionClass(item, parent)
        return parent


    def __insert_sibling_order(self, orphan_children: list[Self], node_position:Self, parent= Self):
        parent.item.children = []

        # I already have a father. Remove me from the list of orphaned children.
        if node_position.parent != parent:
            orphan_children.remove(node_position)

        for child in orphan_children:
            parent.item.children.append(child.item.id)
        parent.children = orphan_children

        return node_position


    def insert_sibling_left(self, item: ItemPosition) -> Self:
        self._is_sibling_left = True

        self._validate(item)
        node_position = None
        orphan_children = []

        # fill list children
        for child in self.parent.children:
            if child == self:
                node_position = self.get_new_node_position(item, self.parent)
                orphan_children.append(node_position)
            orphan_children.append(child)
        return self.__insert_sibling_order(orphan_children, node_position, self.parent)

    def insert_sibling_right(self, item: ItemPosition) -> Self:
        self._is_sibling_right = True

        self._validate(item)
        node_position = None
        orphan_children = []

        # fill list children
        for child in self.parent.children:
            orphan_children.append(child)
            if child == self:
                node_position = self.get_new_node_position(item, self.parent)
                orphan_children.append(node_position)

        return self.__insert_sibling_order(orphan_children, node_position, self.parent)


    def insert_child(self, item: ItemPosition, position_index = int):
        self._validate(item)

        if position_index < 0:
            position_index = 0
        max_children = len(self.children)
        if position_index >= max_children:
            position_index = max_children

        node_position = None
        children = []

        # fill list children
        index = 0
        for child in self.children:
            if index == position_index:
                node_position = self.get_new_node_position(item, self)
                children.append(node_position)
            children.append(child)
            index += 1
        return self.__insert_sibling_order(children, node_position, self)


class RootNodePosition(NodePosition):
    def _validate(self, item: ItemPosition):
        if self.parent:
            raise NodePositionValidationError('Root cannot have a parent.')


class GridNodePosition(NodePosition):
    def _validate(self, item: ItemPosition):
        if self.parent.item.type_ != ItemPositionType.ROOT:
            raise NodePositionValidationError('The GRID parent must be ROOT.')


class TabsNodePosition(NodePosition):
    def _validate(self, item: ItemPosition):
        return


class RowNodePosition(NodePosition):
    def _validate(self, item: ItemPosition):
        return


class TabNodePosition(NodePosition):
    def __init__(self, item: TabItemPosition, parent: Self):
        parent_tabs = self._get_or_insert_parent(TabsItemPosition(), parent, TabsNodePosition)
        super().__init__(item, parent_tabs)

    def _validate(self, item: ItemPosition):
        if self.parent.item.type_ != ItemPositionType.TABS:
            raise NodePositionValidationError('The TAB parent must be TABS.')

    def insert(self, item: ItemPosition) -> Self:
        if item.type_ not in (ItemPositionType.TAB, ItemPositionType.DIVIDER, ItemPositionType.MARKDOWN):
            raise NodePositionValidationError(f'It is only allowed to insert Item Position of the {item.type_} type')
        if item.type_ == ItemPositionType.TAB:
            parent = self._get_or_insert_parent(TabsItemPosition(), self, TabsNodePosition)
            return self.get_new_node_position(item, parent)
        return NodePositionParse.get_instance(item, item.type_, self)


class DividerNodePosistion(NodePosition):
    def _validate(self, item: ItemPosition):
        if item.children:
            raise NodePositionValidationError()


class CheckFreeSpaceMixin:
    def __init__(self, item: ItemPosition, parent: Self = None):
        if not hasattr(self, 'parent'):
            self.parent = parent

        self._validate(item)

        parent = self._get_next_row_free(item, parent)
        super().__init__(item, parent)


    def _get_next_row_free(self, item:ItemPosition, thisnode:NodePosition) ->NodePosition:
        """
            If thisnode does not exist, throw an exception.

            If thisnode is not Row or Tab, return a new row.

            # Handling when item.relocate = False
            checks if thisnode is a row, if yes, checks if there is space,
            otherwise, throw the exception.

            If thisnode is a TAB, create a new row.

            # Handling when item.relocate = True
            Check if thisnode is a row, if yes, check if there is space
            to include the item.

            If the row has full space, check if there are free sibling rows,
            if yes, include the item, otherwise, create a new row.

            If thisnode is a TAB, search all children of type ROW if there is space
            to include the item. If you don't find it, create a new row.

        :param item:
        :param thisnode:
        :return:
        """
        if not thisnode:
            return None
        logger.debug('This node %s(%s)', thisnode.item.id, thisnode.type_)
        if thisnode.type_ == ItemPositionType.ROW:
            return self._linha_livre_a_partir_da_linha(item, thisnode)
        if thisnode.type_ == ItemPositionType.TAB:
            return self._linha_livre_na_aba(item, thisnode)
        if thisnode.type_ == ItemPositionType.COLUMN:
            return thisnode
        logger.debug('Returning a new ROW node, child of this node %s(%s).', thisnode.item.id, thisnode.type_)
        return self.get_new_node_position(RowItemPosition(), thisnode)

    def _linha_livre_a_partir_da_linha(self, item: ItemPosition, linha: NodePosition) -> NodePosition:
        """A própria linha, se couber; senão uma linha irmã com espaço; senão uma linha nova."""
        free_space, total_width = self.have_free_space(linha, item)
        if free_space:
            logger.debug('This node %s(%s) has space, return it.', linha.item.id, linha.type_)
            return linha
        if not item.relocate:
            raise _not_enough_space(total_width)
        for irma in linha.siblings:
            if self.have_free_space(irma, item)[0]:
                logger.debug('This node %s(%s) has no space. Its sibling %s(%s) has free space, so return it.',
                             linha.item.id, linha.type_, irma.item.id, irma.type_)
                return irma
        logger.debug('There are no rows nodes with space. Creating a new row node and returning it.')
        return self.get_new_node_position(RowItemPosition(), linha.parent)

    def _linha_livre_na_aba(self, item: ItemPosition, aba: NodePosition) -> NodePosition:
        """Uma linha da aba com espaço; senão uma linha nova (ou erro, se o item não pode ser realocado)."""
        total_width = None
        for filho in aba.children:
            free_space, total_width = self.have_free_space(filho, item)
            if free_space:
                logger.debug('A child node %s(%s) of thisnode with space was found. Return it.',
                             filho.item.id, filho.type_)
                return filho
        if aba.children and not item.relocate:
            raise _not_enough_space(total_width)
        logger.debug('This node %s(%s) does not have rows available, returning a new row node.',
                     aba.item.id, aba.type_)
        return self.get_new_node_position(RowItemPosition(), aba)

    @classmethod
    def have_free_space(cls, row_node, item):
        total_width = item.width
        try:
            for child in row_node.children:
                if hasattr(child.item, 'width'):
                    total_width += child.item.width
            if total_width <= ItemPosition.MAX_WIDTH:
                return True, total_width
            return False, total_width
        except Exception as err:
            msg = f"""Unexpected error. Unhandled exception.
                err={err}
                row_node={row_node}
                item={item}
            """
            logger.warning(msg)
            return True, total_width

    def _validate(self, item: ItemPosition):
        # Componente com relocate=False não pode estourar a largura da linha. Antes, o erro era
        # levantado dentro de um try/except que só registrava aviso, e a validação nunca valia.
        if not hasattr(item, 'width') or self.parent is None:
            return

        total_width = item.width + sum(getattr(sibling.item, 'width', 0) for sibling in self.siblings)
        if total_width > ItemPosition.MAX_WIDTH and not item.relocate:
            raise _not_enough_space(total_width)


class MarkdownNodePosition(CheckFreeSpaceMixin, NodePosition):
    def __init__(self, item: MarkdownItemPosition, parent: Self = None):
        super().__init__(item, parent)


class ChartNodePosition(CheckFreeSpaceMixin, NodePosition):
    def __init__(self, item: MarkdownItemPosition, parent: Self = None):
        super().__init__(item, parent)


class ColumnNodePosition(NodePosition):
    def __init__(self, item: ColumnItemPosition, parent: Self = None):
        super().__init__(item, parent)

class NodePositionParse:
    PARSE = {
        'ROOT': RootNodePosition,
        'GRID': GridNodePosition,
        'ROW': RowNodePosition,
        'COLUMN': ColumnNodePosition,
        'TABS': TabsNodePosition,
        'TAB': TabNodePosition,
        'MARKDOWN': MarkdownNodePosition,
        'DIVIDER': DividerNodePosistion,
        'CHART': ChartNodePosition

    }

    @classmethod
    def get_instance(cls, item: NodePosition, type_: ItemPositionType, parent: NodePosition):
        NodePositionClass = cls.get_class(str(type_))
        return NodePositionClass(item, parent)

    @classmethod
    def get_class(cls, type_: str):
        return cls.PARSE.get(type_, NodePosition)
