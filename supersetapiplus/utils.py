import re
import unicodedata

import logging
import shortuuid

logger = logging.getLogger(__name__)

def normalize_str(text: str):
    return re.sub('[^A-Za-z0-9_]+', '', unicodedata.normalize('NFKD', text.replace(' ', '_').lower()))

def generate_uuid(_type):
    return f"{_type}-{shortuuid.ShortUUID().random(length=10)}"

def dict_compare(d1, d2):
    d1_keys = set(d1.keys())
    d2_keys = set(d2.keys())
    intersect_keys = d1_keys.intersection(d2_keys)
    added = d1_keys - d2_keys
    removed = d2_keys - d1_keys
    modified = {o: (d1[o], d2[o]) for o in intersect_keys if d1[o] != d2[o]}
    same = set(o for o in intersect_keys if d1[o] == d2[o])
    return added, removed, modified, same

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