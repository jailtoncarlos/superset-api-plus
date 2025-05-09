import logging
import jwt
from superset.security import SupersetSecurityManager
from superset.extensions import security_manager
from werkzeug.exceptions import Unauthorized

logger = logging.getLogger(__name__)

# Chave secreta ou chave pública usada para validar o JWT
JWT_SECRET = "sua-chave-secreta-ou-chave-publica"
JWT_ALGORITHM = "HS256"  # ou "RS256"

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
        except jwt.ExpiredSignatureError:
            raise Unauthorized("Token expirado")
        except jwt.InvalidTokenError:
            raise Unauthorized("Token inválido")

        logger.info(f"[CustomJWT] Token válido. Payload: {payload}")

        # Campos esperados no token (ajuste conforme necessário)
        username = payload.get("email") or payload.get("preferred_username")
        email = payload.get("email")
        first_name = payload.get("given_name", "")
        last_name = payload.get("family_name", "")
        roles = payload.get("roles", [])  # opcional

        if not username or not email:
            raise Unauthorized("Token não contém informações de usuário suficientes.")

        # Cria ou atualiza o usuário local
        user = self.find_user(username=username)
        if not user:
            user = self.add_user(
                username=username,
                first_name=first_name,
                last_name=last_name,
                email=email,
                role=self.find_role("Public"),  # ou role específica
            )
            logger.info(f"[CustomJWT] Usuário criado: {username}")

        return user
