from supersetapiplus.base.enum_str import StringEnum


class CustomNoneType:
    DEFAULT_VALUE = "<NONE>"
    # def __new__(cls):
    #     if not hasattr(cls, '_instance'):
    #         cls._instance = super().__new__(cls)
    #     return cls._instance

    def __repr__(self):
        return self.DEFAULT_VALUE

    def __eq__(self, other):
        return other is None or isinstance(other, CustomNoneType)

    # def __bool__(self):
    #     return False


CUSTOM_NONE = CustomNoneType()


class DatasourceType(StringEnum):
    SLTABLE = "sl_table"
    TABLE = "table"
    DATASET = "dataset"
    QUERY = "query"
    SAVEDQUERY = "saved_query"
    VIEW = "view"