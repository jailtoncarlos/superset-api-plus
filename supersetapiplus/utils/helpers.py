import logging
import re
import unicodedata

import shortuuid

logger = logging.getLogger(__name__)


def normalize_str(text: str) -> str:
    """
    Normaliza uma string removendo acentos e substituindo espaços por sublinhados,
    mantendo apenas letras, números e sublinhados.

    Args:
        text (str): Texto de entrada.

    Returns:
        str: String normalizada.
    """
    return re.sub('[^A-Za-z0-9_]+', '', unicodedata.normalize('NFKD', text.replace(' ', '_').lower()))


def generate_uuid(_type):
    return f"{_type}-{shortuuid.ShortUUID().random(length=10)}"


def compare_objects(obj1, obj2):
    """
    Compara atributos públicos de dois objetos Python, desconsiderando métodos e atributos privados.

    Args:
        obj1 (Any): Primeiro objeto.
        obj2 (Any): Segundo objeto.

    Returns:
        bool: True se todos os atributos públicos forem iguais; False caso contrário.
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
