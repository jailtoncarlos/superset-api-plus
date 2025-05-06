import logging
import re
import unicodedata
from types import NoneType
from typing import Any

import shortuuid

logger = logging.getLogger(__name__)


def normalize_str(text: str):
    return re.sub('[^A-Za-z0-9_]+', '', unicodedata.normalize('NFKD', text.replace(' ', '_').lower()))


def generate_uuid(_type):
    return f"{_type}-{shortuuid.ShortUUID().random(length=10)}"


def detailed_dict_diff(d1, d2):
    """
    Compara dois dicionários e identifica diferenças em termos de chaves e valores.

    Retorna:
        added (set): Chaves presentes em d1 mas não em d2.
        removed (set): Chaves presentes em d2 mas não em d1.
        modified (dict): Chaves presentes em ambos mas com valores diferentes.
        same (set): Chaves presentes em ambos com valores iguais.
    """
    d1_keys = set(d1.keys())
    d2_keys = set(d2.keys())
    intersect_keys = d1_keys.intersection(d2_keys)
    added = d1_keys - d2_keys
    removed = d2_keys - d1_keys
    modified = {o: (d1[o], d2[o]) for o in intersect_keys if d1[o] != d2[o]}
    same = set(o for o in intersect_keys if d1[o] == d2[o])
    return added, removed, modified, same


def dicts_equal_and_all_values_none(dict1: dict[str, Any], dict2: dict[str, Any]) -> bool:
    """
    Verifica se dois dicionários são iguais e se todos os valores de ambos são nulos
    (None ou instâncias de CustomNoneType).

    Args:
        dict1 (dict): Primeiro dicionário.
        dict2 (dict): Segundo dicionário.

    Returns:
        bool: True se os dicionários forem iguais e todos os valores forem nulos; False caso contrário.
    """
    def all_values_null(d: dict) -> bool:
        # Verifica se todos os valores são None ou CustomNoneType
        return all(v is None or isinstance(v, NoneType) for v in d.values())

    return dict1 == dict2 and all_values_null(dict1) and all_values_null(dict2)


def dict_hash(my_dict):
    sorted_items = sorted(my_dict.items())
    hashed_items = [hash(item) for item in sorted_items]
    return hash(tuple(hashed_items))


def compare_objects(obj1, obj2):
    logger.debug(f'compare_objects: {type(obj1)} vs {type(obj2)}')
    for attr in dir(obj1):
        try:
            if not callable(getattr(obj1, attr)) and not attr.startswith("_"):
                if getattr(obj1, attr) != getattr(obj2, attr):
                    logger.debug(f'{attr}: {getattr(obj1, attr)} != {getattr(obj2, attr)}')
                    return False
        except AttributeError as err:
            logger.exception(err)
    return True
