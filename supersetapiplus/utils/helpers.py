import logging
import re
import unicodedata

import shortuuid

logger = logging.getLogger(__name__)


def normalize_str(text: str) -> str:
    """
    Normalize a string by removing accents and replacing spaces with underscores,
    keeping only letters, digits and underscores.

    Args:
        text (str): input text.

    Returns:
        str: normalized string.
    """
    return re.sub('[^A-Za-z0-9_]+', '', unicodedata.normalize('NFKD', text.replace(' ', '_').lower()))


def generate_uuid(_type):
    return f"{_type}-{shortuuid.ShortUUID().random(length=10)}"


def compare_objects(obj1, obj2):
    """
    Compare the public attributes of two Python objects, ignoring methods and private attributes.

    Args:
        obj1 (Any): first object.
        obj2 (Any): second object.

    Returns:
        bool: True if all public attributes are equal; False otherwise.
    """
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
