# Configure logging
import logging

from supersetapiplus.client import SupersetClient  # noqa

# Biblioteca não configura o logging da aplicação (sem basicConfig); só evita o aviso
# "No handlers could be found" quando a aplicação não configura nenhum handler.
logging.getLogger(__name__).addHandler(logging.NullHandler())
