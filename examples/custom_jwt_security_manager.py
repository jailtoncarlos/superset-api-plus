"""Exemplo de configuração do lado do SERVIDOR (superset_config.py), não do cliente.

Security manager do Superset que aceita JWT externo via `Authorization: Bearer <token>`.
Não faz parte do pacote supersetapiplus: depende do próprio `superset` instalado.
"""
import logging
import os

import jwt
from superset.security import SupersetSecurityManager
from werkzeug.exceptions import Unauthorized

logger = logging.getLogger(__name__)

# Chave secreta ou chave pública usada para validar o JWT; nunca fixa no código.
JWT_SECRET = os.environ["SUPERSET_JWT_SECRET"]
JWT_ALGORITHM = os.environ.get("SUPERSET_JWT_ALGORITHM", "HS256")  # ou "RS256"

class CustomJwtSecurityManager(SupersetSecurityManager):
    """
    Custom security manager que aceita JWT via header Authorization: Bearer <token>
    e cria/sincroniza usuários conforme os dados contidos no token.
    """

    def get_user_from_request(self, request):
        """
        Extrai e valida o token JWT do cabeçalho Authorization.
        """
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return None

        token = auth_header[len("Bearer "):]
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        except jwt.ExpiredSignatureError as err:
            raise Unauthorized("Token expirado") from err
        except jwt.InvalidTokenError as err:
            raise Unauthorized("Token inválido") from err

        logger.debug("[CustomJWT] Token válido para %s.", payload.get("email") or payload.get("preferred_username"))

        # Campos esperados no token (ajuste conforme necessário)
        username = payload.get("email") or payload.get("preferred_username")
        email = payload.get("email")
        first_name = payload.get("given_name", "")
        last_name = payload.get("family_name", "")
        role_names = payload.get("roles") or []  # opcional

        if not username or not email:
            raise Unauthorized("Token não contém informações de usuário suficientes.")

        # Cria ou atualiza o usuário local
        user = self.find_user(username=username)
        if not user:
            # Primeiro papel do token que exista no Superset; sem nenhum, "Public".
            role = next((r for r in map(self.find_role, role_names) if r), None) or self.find_role("Public")
            user = self.add_user(
                username=username,
                first_name=first_name,
                last_name=last_name,
                email=email,
                role=role,
            )
            logger.info(f"[CustomJWT] Usuário criado: {username}")

        return user
