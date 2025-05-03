"""
Módulo typing.py

Este módulo define tipos genéricos auxiliares utilizados na serialização e deserialização
de objetos no framework `supersetapiplus`. Os tipos aqui definidos são fundamentais
para o controle de exportação seletiva de atributos e manipulação de campos opcionais
em modelos que herdam da classe base `Object`.

Classes:
    NotToJson[T]: Tipo genérico que encapsula valores que não devem ser serializados
                  no JSON final (omitidos na exportação).
    Optional[T]: Tipo genérico que encapsula valores opcionais, aplicando lógica
                 personalizada na exclusão de campos nulos ou com valor padrão durante
                 a serialização para JSON.

Aliases:
    FilterValue: Tipo auxiliar que representa os tipos básicos aceitos em filtros (bool, datetime, float, int, str).
    FilterValues: Tipo que aceita um único FilterValue, uma lista ou uma tupla desses valores.
"""

from datetime import datetime
from typing import Union, Generic, TypeVar

T = TypeVar('T')


class SerializableNotToJson(Generic[T]):
    """
    Classe genérica que encapsula um valor que **não deve ser incluído na serialização JSON**.

    Esta classe é utilizada nos modelos que herdam de `Object`, em conjunto com a
    lógica do método `remove_exclude_keys`, para excluir automaticamente campos do
    JSON de saída.

    Parâmetros:
        value (T): Valor encapsulado que será utilizado internamente, mas não exportado.

    Métodos:
        get() -> T:
            Retorna o valor encapsulado.
    """

    def __init__(self, value: T):
        self.value = value

    def get(self) -> T:
        """Retorna o valor encapsulado."""
        return self.value


class SerializableOptional(Generic[T]):
    """
    Classe genérica que encapsula um valor **opcional** com lógica de exclusão condicional
    durante a serialização JSON.

    Ao contrário do `typing.Optional`, esta classe permite que o método `remove_exclude_keys`
    exclua o campo da saída JSON caso:
      - O valor seja `None` e o campo não tenha valor padrão.
      - O valor seja igual ao valor padrão definido na dataclass.

    Parâmetros:
        value (T): Valor encapsulado, que pode ser opcional.

    Métodos:
        get() -> T:
            Retorna o valor encapsulado.
    """

    def __init__(self, value: T):
        self.value = value

    def get(self) -> T:
        """Retorna o valor encapsulado."""
        return self.value


#: Tipo auxiliar para valores simples aceitos em filtros.
FilterValue = Union[bool, datetime, float, int, str]

#: Tipo auxiliar para representar múltiplos valores em filtros (valor único, lista ou tupla).
FilterValues = Union[FilterValue, list[FilterValue], tuple[FilterValue]]
