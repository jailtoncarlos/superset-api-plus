import dataclasses


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