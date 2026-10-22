import logging
import re
import sys

logger = logging.getLogger(__name__)


class ParseMixin:
    """
    Mixin that provides dynamic class resolution based on a 'type' identifier.
    """

    @classmethod
    def get_instance(cls, **kwargs):
        """
        Instantiate a class determined by the 'type' or 'type_' keyword.

        Args:
            **kwargs: Must include 'type' or 'type_' specifying the viz_type.

        Returns:
            An instance of the resolved class.

        Raises:
            ValueError: If neither 'type' nor 'type_' is provided or they are empty.
            ImportError: If the module cannot be found in sys.modules.
            NameError: If the resolved class name is not present in the module.
        """
        type_ = kwargs.get('type') or kwargs.get('type_')
        if not type_:
            raise ValueError("The 'type_' argument must not be empty.")
        ParseClass = cls.get_class(type_)
        return ParseClass(**kwargs)

    @classmethod
    def get_class(cls, type_: str, module_name: str = None):
        """
        Resolve and return the class corresponding to the given viz_type.

        The class name is built by:
        1. Capitalizing the first letter of type_.
        2. Converting any '_x' sequence to 'X' (uppercase) and removing the underscore.
        3. Appending the mixin's class name as a suffix.

        Example:
            type_='box_plot', suffix='Chart' → 'BoxPlotChart'

        Args:
            type_ (str): The viz_type identifier (must match module filename).
            module_name (str, optional): The module path where the class is defined.
                                         Defaults to this mixin's module.

        Returns:
            type: The resolved class object.

        Raises:
            ImportError: If module_name is not found in sys.modules.
            NameError: If the constructed class name is not found in the module.
        """
        if not module_name:
            module_name = cls.__module__
        suffix = cls.__name__

        # Build class name by capitalizing and removing underscores:
        class_name = re.sub(
            r'_(.)',
            lambda m: m.group(1).upper(),
            f'{type_.capitalize()}{suffix}'
        )

        # 1) Verify module exists
        try:
            module = sys.modules[module_name]
        except KeyError as e:
            message = (
                f"Module '{module_name}' not found. "
                f"Expected the module file to be named '{type_}.py'."
            )
            logger.error(message)
            raise ImportError(message) from e

        # 2) Verify class exists in module
        try:
            cls_obj = getattr(module, class_name)
        except AttributeError as e:
            message = (
                f"Class '{class_name}' not found in module '{module_name}'. "
                f"Expected class name to match viz_type '{type_}' by capitalizing the first letter "
                "and each letter following an underscore, then removing underscores."
            )
            logger.error(message)
            raise NameError(message) from e

        return cls_obj
