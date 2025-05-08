import sys
import re


class ParseMixin:
    @classmethod
    def get_instance(cls, **kwargs):
        type_ = kwargs.get('type') or kwargs.get('type_')
        if not type_:
            raise Exception(f'type_ argument cannot be empty.')
        ParseClass = cls.get_class(type_)
        return ParseClass(**kwargs)

    @classmethod
    def get_class(cls, type_: str, module_name: str = None):
        if not module_name:
            module_name = cls.__module__
        suffix = cls.__name__

        # Convert the initial letters after "_" to uppercase and then remove the "_" characters.
        class_name = re.sub(r'_(.)', lambda m: m.group(1).upper(), f'{type_.capitalize()}{suffix}')

        return getattr(sys.modules[module_name], class_name, None)