"""Base classes."""
import dataclasses
import logging
from abc import abstractmethod, ABC
from enum import Enum

from typing_extensions import Self

try:
    from functools import cached_property
except ImportError:  # pragma: no cover
    # Python<3.8
    from cached_property import cached_property

import json
import os.path
from pathlib import Path
from typing import List, Union, Dict, get_origin

import yaml
from requests import HTTPError

from supersetapiplus.exceptions import BadRequestError, ComplexBadRequestError, MultipleFound, NotFound, \
    LoadJsonError
from supersetapiplus.base.parse import ParseMixin
from supersetapiplus.client import QueryStringFilter
from supersetapiplus.typing import SerializableNotToJson, SerializableOptional
from supersetapiplus.utils import dict_hash

logger = logging.getLogger(__name__)


def object_field(*, cls=None, default=dataclasses.MISSING, default_factory=dataclasses.MISSING,
                 init=True, repr=True, hash=None, compare=True,
                 metadata=None, kw_only=dataclasses.MISSING,
                 dict_left=False, dict_right=False):
    """
    Cria um campo personalizado para uso em dataclasses, adicionando suporte a metadados
    especializados utilizados no framework supersetapiplus, como serialização customizada
    de dicionários com chaves ou valores do tipo Object.

    Essa função encapsula a chamada a `dataclasses.field`, adicionando metadados
    úteis para desserialização automática de estruturas JSON aninhadas.

    Parâmetros:
        cls (type, opcional): Classe que herda de `Object` associada ao campo. Útil para
            instanciar objetos aninhados durante o `from_json`.
        default: Valor padrão do campo. Incompatível com `default_factory` se ambos forem definidos.
        default_factory: Função que retorna o valor padrão do campo. Não pode ser usado com `default`.
        init (bool): Se o campo deve ser incluído no método `__init__`. Padrão é True.
        repr (bool): Se o campo deve ser incluído na representação gerada por `__repr__`. Padrão é True.
        hash (bool | None): Se o campo deve ser considerado no cálculo de hash. Se None, segue o padrão do `dataclass`.
        compare (bool): Se o campo deve ser considerado em operações de comparação. Padrão é True.
        metadata (dict, opcional): Dicionário com metadados adicionais. Pode ser usado por lógicas externas.
        kw_only (bool): Define se o campo deve ser obrigatório como keyword-only no `__init__`. Introduzido no Python 3.10.
        dict_left (bool): Se True, indica que o campo é um dicionário onde a chave é uma instância de `Object`.
        dict_right (bool): Se True, indica que o campo é um dicionário onde o valor é uma instância de `Object`.

    Retorna:
        dataclasses.Field: Instância configurada de campo para uso em uma dataclass.

    Levanta:
        ValueError: Caso `default` e `default_factory` sejam definidos simultaneamente.
    """
    # Garante que apenas um entre default e default_factory seja definido
    if default is not dataclasses.MISSING and default_factory is not dataclasses.MISSING:
        raise ValueError('cannot specify both default and default_factory')

    # Inicializa metadados, garantindo inclusão das chaves específicas
    metadata = metadata or {}
    metadata.update({
        "cls": cls,
        "dict_left": dict_left,
        "dict_right": dict_right,
    })

    # Retorna o campo com todos os parâmetros configurados
    return dataclasses.field(
        default=default,
        default_factory=default_factory,
        init=init,
        repr=repr,
        hash=hash,
        compare=compare,
        metadata=metadata,
        kw_only=kw_only
    )


class ObjectDecoder(json.JSONEncoder):
    """
    Codificador JSON personalizado para serializar objetos que contenham instâncias de Enum.

    Essa classe sobrescreve o método `default` do `json.JSONEncoder` para garantir que
    valores do tipo `Enum` sejam convertidos para suas representações em string
    (usualmente `value`), facilitando a serialização de objetos que utilizam Enums
    como atributos.

    Exemplo:
        >>> class Status(Enum):
        ...     OK = "ok"
        ...     FAIL = "fail"
        >>> json.dumps({'status': Status.OK}, cls=ObjectDecoder)
        '{"status": "ok"}'

    Métodos:
        default(obj): Retorna `str(obj.value)` se `obj` for uma instância de Enum,
                      caso contrário, delega para o comportamento padrão.
    """

    def default(self, obj):
        # Converte instâncias de Enum para o valor associado em formato string
        if isinstance(obj, Enum):
            return str(obj.value)
        # Para outros tipos, usa a implementação padrão do JSONEncoder
        return super().default(obj)


def json_field(**kwargs):
    """
    Cria um campo para dataclass que será utilizado para armazenar estruturas JSON.

    Esse campo é configurado para não aparecer na representação (`repr=False`) e
    recebe um valor padrão `None`, caso nenhum `default` seja explicitamente fornecido.

    Esta função é útil para atributos que armazenam strings JSON ou objetos
    que serão posteriormente serializados/desserializados.

    Args:
        **kwargs: Argumentos adicionais para o construtor `dataclasses.field`.

    Returns:
        dataclasses.Field: Campo configurado para uso em dataclass.

    Exemplo:
        class Example(Object):
            payload: dict = json_field()
    """
    if not kwargs.get('default'):
        # Define valor padrão como None se não for explicitamente informado
        kwargs['default'] = None

    # Cria o campo ocultando-o da representação textual da instância
    return dataclasses.field(repr=False, **kwargs)


def default_string(**kwargs):
    """
    Cria um campo para dataclass com valor padrão do tipo string vazia ('') e
    oculto na representação textual do objeto (`repr=False`).

    Esta função é usada para atributos opcionais de string que devem iniciar
    com valor vazio por padrão, sem a necessidade de definir `default=''` explicitamente
    em cada campo.

    Args:
        **kwargs: Argumentos adicionais passados ao construtor `dataclasses.field`.

    Returns:
        dataclasses.Field: Campo configurado com `default=''` e `repr=False`.

    Exemplo:
        class Example(Object):
            nome: str = default_string()
    """
    if not kwargs.get('default'):
        # Define string vazia como valor padrão se não fornecido explicitamente
        kwargs['default'] = ''

    # Cria o campo ocultando-o da representação textual da instância
    return dataclasses.field(repr=False, **kwargs)


def default_bool(**kwargs):
    """
    Cria um campo do tipo booleano para dataclass com valor padrão `False`
    e oculto na representação textual do objeto (`repr=False`).

    Esta função é útil para evitar repetições ao definir campos booleanos
    opcionais que devem iniciar como `False`.

    Args:
        **kwargs: Argumentos adicionais para o construtor `dataclasses.field`.

    Returns:
        dataclasses.Field: Campo booleano configurado com `default=False` e `repr=False`.

    Exemplo:
        class Example(Object):
            ativo: bool = default_bool()
    """
    # Se nenhum valor padrão for fornecido explicitamente, usa False
    if not kwargs.get('default'):
        kwargs['default'] = False

    # Cria o campo com `repr=False` para não ser exibido em __repr__
    return dataclasses.field(repr=False, **kwargs)


def raise_for_status(response):
    """
    Verifica o status da resposta HTTP e, em caso de erro, lança exceções detalhadas.

    Esta função estende o comportamento padrão de `requests.Response.raise_for_status()`
    adicionando logs detalhados da requisição e da resposta, além de lançar exceções
    personalizadas baseadas no conteúdo retornado pela API.

    Exceções levantadas:
        - BadRequestError: Se a resposta contiver uma mensagem de erro simples.
        - ComplexBadRequestError: Se a resposta contiver múltiplos erros detalhados.
        - HTTPError: Para outros erros HTTP não tratados especificamente.

    Args:
        response (requests.Response): Objeto de resposta da biblioteca `requests`.

    Raises:
        BadRequestError: Quando a resposta HTTP contém um campo `message`.
        ComplexBadRequestError: Quando a resposta HTTP contém um campo `errors`.
        HTTPError: Exceção genérica lançada pelo método `raise_for_status()`.
    """
    try:
        response.raise_for_status()
    except HTTPError as e:
        request = response.request
        request_headers = '\n'.join(f'{k}: {v}' for k, v in request.headers.items())
        response_headers = '\n'.join(f'{k}: {v}' for k, v in response.headers.items())

        # Tenta obter o corpo da resposta como texto
        try:
            response_body = response.text
        except Exception:
            response_body = "<não foi possível decodificar o corpo da resposta>"

        # Log detalhado da requisição e resposta
        logger.error("Erro na requisição HTTP")
        logger.error(f"Request URL: {request.url}")
        logger.error(f"Request Method: {request.method}")
        logger.error(f"Request Headers:\n{request_headers}")
        logger.error(f"Request Body:\n{request.body or '<vazio>'}")
        logger.error(f"Response Status Code: {response.status_code}")
        logger.error(f"Response Headers:\n{response_headers}")
        logger.error(f"Response Body:\n{response_body}")

        # Tentativas de extrair mensagens específicas da resposta JSON
        try:
            error_msg = response.json().get("message")
        except Exception:
            error_msg = None

        try:
            errors = response.json().get("errors")
        except Exception:
            errors = None

        # Lança exceções específicas baseadas nos campos presentes
        if errors:
            raise ComplexBadRequestError(*e.args, request=request, response=response, errors=errors) from None
        elif error_msg:
            raise BadRequestError(*e.args, request=request, response=response, message=error_msg) from None
        else:
            raise e


class Object(ParseMixin, ABC):
    """
    Classe base abstrata para representação de objetos que interagem com a API do Superset.

    Esta classe fornece funcionalidades para:
    - Serialização e desserialização de objetos via JSON.
    - Validação de dados.
    - Conversão para dicionário (`to_dict`) e JSON (`to_json`).
    - Suporte a campos extras não modelados diretamente.
    - Comparação, hashing e carregamento de dados.

    A classe assume que cada subclasse será uma `dataclass` com campos definidos para refletir a estrutura esperada da API.

    Attributes:
        _factory: Referência à factory que gerencia instâncias desse objeto.
        JSON_FIELDS (List[str]): Lista de campos que devem ser serializados como JSON.
        _extra_fields (Dict): Armazena campos não mapeados diretamente nos atributos da classe.
    """
    _factory = None
    JSON_FIELDS = []

    _extra_fields: Dict = {}

    def validate(self, data: dict):
        raise NotImplementedError("validate method not implemented")

    def __post_init__(self):
        """
        Executa ações pós-inicialização para instâncias da classe Object.

        Este método é chamado automaticamente após a criação de instâncias de dataclasses.
        Ele possui duas responsabilidades principais:

        1. Desserializar os campos definidos em `JSON_FIELDS` que tenham sido passados como strings.
           Esses campos são esperados em formato JSON e, portanto, convertidos para estruturas Python.

        2. Atribuir valores padrão explícitos para campos que:
            - Possuem valor padrão definido.
            - Não foram preenchidos (valor `None`) durante a instância.
            - Não são campos do tipo `SerializableOptional`.

        Isso garante que os campos obrigatórios possuam valores apropriados,
        melhorando a consistência do estado interno do objeto logo após sua criação.
        """

        # Converte os campos definidos como JSON_FIELDS que foram passados como string em dicionários Python
        for f in self.JSON_FIELDS:
            value = getattr(self, f) or "{}"
            if isinstance(value, str):
                setattr(self, f, json.loads(value))

        # Itera sobre todos os campos da dataclass
        for field in self.fields():
            # Se o campo tem valor padrão, está como None e não é SerializableOptional, define seu valor padrão
            if not isinstance(field.default, dataclasses._MISSING_TYPE) \
                    and getattr(self, field.name) is None \
                    and not get_origin(field.type) is SerializableOptional:
                setattr(self, field.name, field.default)

    @property
    def extra_fields(self):
        return self._extra_fields

    def __eq__(self, other):
        """
        Compara a instância atual com outro objeto para verificar igualdade estrutural.

        Este método sobrescreve o operador `==` para comparar objetos do tipo `Object`.
        A comparação é feita com base nos atributos internos (`__dict__`) de cada objeto, com exceção
        do atributo `_extra_fields`, que é ignorado por não compor o núcleo da estrutura serializável.

        Args:
            other (object): Objeto a ser comparado.

        Returns:
            bool: `True` se os objetos forem equivalentes em todos os atributos relevantes; `False` caso contrário.
                  Retorna `NotImplemented` se o objeto comparado não for do mesmo tipo.

        Exceções:
            NotImplementedError: Caso o objeto `other` não seja do mesmo tipo da instância atual.
        """

        # Verifica se os objetos são da mesma classe. Caso contrário, não implementa comparação.
        if not isinstance(other, type(self)):
            return NotImplementedError()

        # Obtém os atributos da instância atual e remove o campo _extra_fields da comparação
        dict_self = vars(self)
        dict_self.pop('_extra_fields', None)

        # Obtém os atributos do objeto comparado e remove o campo _extra_fields da comparação
        dict_other = vars(other)
        dict_other.pop('_extra_fields', None)

        # Retorna True se os dicionários forem iguais (atributos equivalentes)
        return dict_self == dict_other

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        """
        Gera um hash único para a instância da classe com base em seus atributos internos.

        Este método sobrescreve o comportamento padrão de `__hash__` para permitir que
        objetos da classe `Object` possam ser utilizados como chaves em dicionários ou
        armazenados em conjuntos (`set`). O campo `_extra_fields` é explicitamente removido
        da base de cálculo do hash por não fazer parte da estrutura essencial serializável do objeto.

        Returns:
            int: Valor de hash calculado com base nos atributos principais do objeto.
        """

        # Obtém todos os atributos da instância
        dict_self = vars(self)

        # Remove o campo _extra_fields para garantir consistência no hash
        dict_self.pop('_extra_fields', None)

        # Gera o hash a partir da função utilitária definida no projeto
        return dict_hash(dict_self)

    @classmethod
    def fields(cls) -> set:
        """Get field names."""
        _fields = set()

        for n, f in cls.__dataclass_fields__.items():
            if isinstance(f, dataclasses.Field):
                _fields.add(f)

        _fields.update(dataclasses.fields(cls))

        return _fields

    @classmethod
    def get_field(cls, name):
        for f in cls.fields():
            if f.name == name:
                return f

    @classmethod
    def field_names(cls) -> list:
        """Get field names."""
        fields = []
        for f in cls.fields():
            if not isinstance(f.default, Object):
                fields.append(f.name)
        return fields

    @classmethod
    def required_fields(cls, data) -> dict:
        rdata = {}
        for f in cls.fields():
            if f.default is dataclasses.MISSING and not isinstance(f.default, Object):
                rdata[f.name] = data.get(f.name)
        return rdata

    @classmethod
    def __get_extra_fields(cls, data:dict) -> dict:
        if not data:
            return {}

        field_names = set(cls.field_names())

        data_keys = set(data.keys())
        extra_fields_keys = data_keys - field_names
        extra_fields = {}
        for field_name in extra_fields_keys:
            extra_fields[field_name] = data.pop(field_name)

        return extra_fields

    @classmethod
    def _subclass_object(cls, field: dataclasses.Field):
        # return field.metadata.get("cls")
        """
        Retorna a classe que herda de Object definida em default_factory do campo.

        Isso evita problemas com tipos genéricos (List, Optional, etc).

        Args:
            field (Field): Um campo de dataclass

        Returns:
            Classe que herda de Object, ou None
        """
        if field.metadata.get("cls"):
            return field.metadata.get("cls")

        default_factory = getattr(field, 'default_factory', None)

        if default_factory and default_factory is not dataclasses.MISSING:
            if isinstance(default_factory, type) and issubclass(default_factory, Object):
                return default_factory

        return None

    @classmethod
    def from_json(cls, data: dict) -> Self:
        extra_fields = cls.__get_extra_fields(data)
        field_name = None
        field_value = None
        data_value = None
        try:
            # if not isinstance(data, dict):
            #     return data

            obj = cls(**data)

            for field_name in cls.JSON_FIELDS:
                logger.debug(f'field_name: {field_name} found in JSON_FIELDS')
                data_value = data.get(field_name)
                if isinstance(data_value, str):
                    field = cls.get_field(field_name)
                    ObjectClass = cls._subclass_object(field)
                    if ObjectClass:
                        value = ObjectClass.from_json(json.loads(data[field_name]))
                    else:
                        value = json.loads(data[field_name])

                    setattr(obj, field_name, value)

            for field_name, data_value in data.items():
                logger.debug(f'field_name: {field_name}; data_value type: {type(data_value)}; data_value: {data_value}')
                if field_name in cls.JSON_FIELDS:
                    continue
                if isinstance(data_value, dict):
                    field = cls.get_field(field_name)
                    ObjectClass = cls._subclass_object(field)
                    value = None
                    if ObjectClass and field.metadata.get('dict_right'):
                        value = {}
                        for k, field_value in data_value.items():
                            value[k] = ObjectClass.from_json(field_value)
                    elif ObjectClass:
                        value = ObjectClass.from_json(data_value)
                    else:
                        value = data_value
                    setattr(obj, field_name, value)
                elif isinstance(data_value, list):
                    field = cls.get_field(field_name)
                    ObjectClass = cls._subclass_object(field)
                    value = []
                    for field_value in data_value:
                        if ObjectClass and isinstance(field_value, dict):
                            try:
                                value.append(ObjectClass.from_json(field_value))
                            except Exception as err:
                                msg = f"""unhandled exception: {err}
                                    cls={cls}
                                    field_name={field_name}
                                    data_value={data_value}
                                    data={data}
                                    extra_fields={extra_fields}
                                """
                                logger.warning(msg)
                                raise
                        else:
                            value.append(field_value)
                    setattr(obj, field_name, value)
                else:
                    setattr(obj, field_name, data_value)

            obj._extra_fields = extra_fields
        except Exception as err:
            msg = f"""Error deserializing list item
                cls={cls}
                field_name={field_name}
                item_value={field_value}
                data_value={data_value}
                data={data}
                extra_fields={extra_fields}
                causa original: {err}
            """
            logger.exception(msg)
            raise LoadJsonError(msg) from err
        return obj

    @classmethod
    def remove_exclude_keys(cls, data, parent_field_name=''):
        def is_exclude(field_name, parent_field, data):
            field = cls.get_field(field_name)
            _is_exclude = False
            try:
                if not field and parent_field:
                    ObjectClass = cls._subclass_object(parent_field)
                    field = ObjectClass.get_field(field_name)
                if get_origin(field.type) is SerializableOptional:
                    if not data[field.name] and field.default is dataclasses.MISSING:
                        _is_exclude = True
                    elif field.default == data[field.name]:
                        _is_exclude = True
                    else:
                        _is_exclude = False
                if get_origin(field.type) is SerializableNotToJson:
                    _is_exclude = True
            except Exception:
                pass
            return _is_exclude

        if isinstance(data, list):
            # If it is a list, we apply the function to each element in the list
            newdata = []
            for item in data:
                if not is_exclude(parent_field_name, parent_field_name, data):
                    newdata.append(cls.remove_exclude_keys(item, parent_field_name))
            return newdata
        if isinstance(data, dict):
            # If it's a dictionary, we loop through its keys and values
            return {
                key: cls.remove_exclude_keys(value, key) for key, value in data.items()
                if not is_exclude(key, cls.get_field(parent_field_name), data)
            }
        # If it is neither a list nor a dictionary, we return the value as is
        return data

    def to_dict(self, columns=[]) -> dict:
        def prepare_value_tuple(field_value):
            values_data = []
            if isinstance(field_value, tuple):
                l1 = field_value[0]
                l2 = field_value[1]
                if isinstance(field_value[0], Object):
                    l1 = field_value[0].to_dict()
                elif isinstance(field_value[1], Object):
                    l2 = field_value[1].to_dict()
                elif isinstance(field_value[0], Enum):
                    l1 = str(field_value[0])
                elif isinstance(field_value[1], Enum):
                    l2 = str(field_value[0])
                values_data.append((l1, l2))
            return values_data

        columns_names = set(columns or [])
        columns_names.update(self.field_names())
        data = {}
        for c in columns_names:
            if not hasattr(self, c):
                # Column that is not implemented yet
                continue
            value = getattr(self, c)
            if isinstance(value, Enum):
                value = str(value)
            elif value and isinstance(value, Object):
                value = value.to_dict(columns)
            elif value and isinstance(value, list):
                values_data = []
                for field_value in value:
                    if isinstance(field_value, Object):
                        values_data.append(field_value.to_dict())
                    elif isinstance(field_value, tuple):
                        values_data = prepare_value_tuple(field_value)
                    elif isinstance(field_value, Enum):
                        values_data.append(str(field_value))
                    else:
                        values_data.append(field_value)
                    value = values_data
            elif value and isinstance(value, dict):
                field = self.get_field(c)
                ObjectClass = self._subclass_object(field)
                if ObjectClass:
                    _value = {}
                    if field.metadata.get('dict_left'):
                        for obj, value_ in value.items():
                            _value[obj.to_dict()] = value_
                    elif field.metadata.get('dict_right'):
                        for k, obj in value.items():
                            _value[k] = obj.to_dict()
                    value = _value
            elif value and isinstance(value, tuple):
                value = prepare_value_tuple(value)
            data[c] = value
            # logger.debug(f'return data {data}')
        return data

#    dictionary = {'fruit': {"Grapes": "10", "color": "green"}, 'vegetable': {"chilli": "4", "color": "red"},}
#    json.dumps(dictionary, indent=3)
#    obj.to_json()
#   json.dumps(self.to_dict(columns), indent=3)
#   print(json.dumps(self.to_dict(columns), indent=3))

    def to_json(self, columns=[]) -> dict:
        data = self.to_dict(columns)
        self.validate(data)

        for field in self.JSON_FIELDS:
            obj = getattr(self, field)
            if isinstance(obj, Object):
                data[field] = json.dumps(obj.to_json(), cls=ObjectDecoder)
            elif isinstance(obj, dict):
                data[field] = json.dumps(data[field], cls=ObjectDecoder)

        copydata = self.remove_exclude_keys(data)

        if copydata.get('extra_fields'):
            copydata.pop('extra_fields')
        logger.debug(f'return data {copydata}')
        return copydata

    @property
    def base_url(self) -> str:
        return self._factory.client.join_urls(self._factory.base_url, self.id)

    def export(self, path: Union[Path, str]) -> None:
        """Export object to path"""
        self._factory.export(ids=[self.id], path=path)

    def fetch(self) -> None:
        """Fetch additional object information."""
        field_names = self.field_names()

        client = self._factory.client
        response = client.get(self.base_url)
        o = response.json().get("result")
        for k, v in o.items():
            if k in field_names:
                if k in self.JSON_FIELDS:
                    setattr(self, k, json.loads(v or "{}"))
                else:
                    setattr(self, k, v)

    def save(self) -> None:
        """Save object information."""
        o = self.to_json(columns=self._factory.edit_columns)
        logger.info(f'payload: {o}')

        response = self._factory.client.put(self.base_url, json=o)
        raise_for_status(response)
        logger.info(f'response: {response.json()}')

    def delete(self) -> bool:
        return self._factory.delete(id=self.id)

    def get_request_response(self):
        jdict = self._request_response.json()
        for field_name in self.JSON_FIELDS:
            jdict['result'][field_name] = json.loads(jdict['result'][field_name])
        return jdict


class ObjectFactories(ABC):
    endpoint = ""

    _INFO_QUERY = {"keys": ["add_columns", "edit_columns"]}

    def __init__(self, client):
        """Create a new Dashboards endpoint.

        Args:
            client (client): superset client
        """
        self.client = client

    @abstractmethod
    def _default_object_class(self) -> type[Object]:
        ...

    def get_base_object(self, data):
        type_ = data['viz_type']
        if type_:
            m = self._default_object_class().__module__.split('.')
            m.pop(-1)
            m.append(type_)
            module_name = '.'.join(m)
            return self._default_object_class().get_class(type_, module_name)
        return self._default_object_class()

    @cached_property
    def _infos(self):
        # Get infos
        response = self.client.get(self.info_url, params={"q": json.dumps(self._INFO_QUERY)})
        raise_for_status(response)
        return response.json()

    @property
    def add_columns(self):
        return [e.get("name") for e in self._infos.get("add_columns", [])]

    @property
    def edit_columns(self):
        return [e.get("name") for e in self._infos.get("edit_columns", [])]

    @property
    def base_url(self):
        """Base url for these objects."""
        url = self.client.join_urls(self.client.base_url, self.endpoint)
        logger.info(f'url: {url}')
        return url

    @property
    def info_url(self):
        return self.client.join_urls(self.base_url, "_info")

    @property
    def import_url(self):
        return self.client.join_urls(self.base_url, "import/")

    @property
    def export_url(self):
        return self.client.join_urls(self.base_url, "export/")

    def get(self, id: str):
        """Get an object by id."""
        url = self.client.join_urls(self.base_url, id)
        logger.info(f'url: {url}')

        response = self.client.get(url)
        raise_for_status(response)

        result = response.json()
        logger.info(f'response: {result}')

        data_result = result['result']

        data_result["id"] = result.get('id', data_result.get('id', id))
        BaseClass = self.get_base_object(data_result)

        object = BaseClass.from_json(data_result)
        object._request_response = response
        object._factory = self

        return object

    def find(self, filter:QueryStringFilter, columns:List[str]=[], page_size: int = 100, page: int = 0):
        """Find and get objects from api."""

        response = self.client.find(self.base_url, filter, columns, page_size, page)

        objects = []
        for data in response.get("result"):
            o = self.get_base_object(data).from_json(data)
            o._factory = self
            objects.append(o)

        return objects

    def count(self):
        """Count objects."""
        response = self.client.get(self.base_url)
        raise_for_status(response)
        return response.json()["count"]

    def find_one(self, filter:QueryStringFilter, columns:List[str]=[]):
        """Find only object or raise an Exception."""
        objects = self.find(filter, columns)
        if len(objects) == 0:
            raise NotFound(f"No {self.get_base_object().__name__} found")
        if len(objects) > 1:
            raise MultipleFound(f"Multiple {self.get_base_object().__name__} found")
        return objects[0]

    def add(self, obj) -> int:
        """Create an object on remote."""
        o = obj.to_json(columns=self.add_columns)
        logger.info(f'payload: {o}')

        response = self.client.post(self.base_url, json=o)
        raise_for_status(response)
        result = response.json()
        logger.info(f'response: {result}')

        obj.id = result.get("id")
        obj._factory = self
        return obj.id

    def export(self, ids: List[int], path: Union[Path, str]) -> None:
        """Export object into an importable file"""
        ids_array = ",".join([str(i) for i in ids])
        response = self.client.get(self.export_url, params={"q": f"[{ids_array}]"})

        raise_for_status(response)

        content_type = response.headers["content-type"].strip()
        if content_type.startswith("application/text"):  # pragma: no cover
            # Superset 1.x
            data = yaml.load(response.text, Loader=yaml.FullLoader)
            with open(path, "w", encoding="utf-8") as f:
                yaml.dump(data, f, default_flow_style=False)
            return
        if content_type.startswith("application/json"):  # pragma: no cover
            # Superset 1.x
            data = response.json()
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
            return
        if content_type.startswith("application/zip"):
            data = response.content
            with open(path, "wb") as f:
                f.write(data)
            return
        raise ValueError(f"Unknown content type {content_type}")

    def delete(self, id: int) -> bool:
        """Delete a object on remote."""
        url = self.client.join_urls(self.base_url, id)
        logger.info(f'url: {url}')
        response = self.client.delete(url)
        raise_for_status(response)
        logger.info(f'response: {response.json()}')
        return response.json().get("message") == "OK"

    def import_file(self, file_path, overwrite=False, passwords=None) -> dict:
        """Import a file on remote.

        :param file_path: Path to a JSON or ZIP file containing the import data
        :param overwrite: If True, overwrite existing remote entities
        :param passwords: JSON map of passwords for each featured database in
        the file. If the ZIP includes a database config in the path
        databases/MyDatabase.yaml, the password should be provided in the
        following format: {"MyDatabase": "my_password"}
        """
        data = {"overwrite": json.dumps(overwrite)}
        passwords = {f"databases/{db}.yaml": pwd for db, pwd in (passwords or {}).items()}
        file_name = os.path.split(file_path)[-1]
        file_ext = os.path.splitext(file_name)[-1].lstrip(".").lower()
        with open(file_path, "rb") as f:
            files = {
                "formData": (file_name, f, f"application/{file_ext}"),
                "passwords": (None, json.dumps(passwords), None),
            }
            response = self.client.post(
                self.import_url,
                files=files,
                data=data,
                headers={"Accept": "application/json"},
            )
        raise_for_status(response)

        # If import is successful, the following is returned: {'message': 'OK'}
        return response.json().get("message") == "OK"
