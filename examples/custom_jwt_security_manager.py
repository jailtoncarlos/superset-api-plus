"""Example of SERVER-side configuration (superset_config.py), not client-side.

Superset security manager that accepts an external JWT via `Authorization: Bearer <token>`.
It is not part of the supersetapiplus package: it depends on `superset` itself being installed.
"""
import logging
import os

import jwt
from superset.security import SupersetSecurityManager
from werkzeug.exceptions import Unauthorized

logger = logging.getLogger(__name__)

# Secret key or public key used to validate the JWT; never hardcoded.
JWT_SECRET = os.environ["SUPERSET_JWT_SECRET"]
JWT_ALGORITHM = os.environ.get("SUPERSET_JWT_ALGORITHM", "HS256")  # or "RS256"

class CustomJwtSecurityManager(SupersetSecurityManager):
    """
    Custom security manager that accepts a JWT via the Authorization: Bearer <token> header
    and creates/syncs users from the data contained in the token.
    """

    def get_user_from_request(self, request):
        """
        Extract and validate the JWT from the Authorization header.
        """
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return None

        token = auth_header[len("Bearer "):]
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        except jwt.ExpiredSignatureError as err:
            raise Unauthorized("Token expired") from err
        except jwt.InvalidTokenError as err:
            raise Unauthorized("Invalid token") from err

        logger.debug("[CustomJWT] Valid token for %s.", payload.get("email") or payload.get("preferred_username"))

        # Fields expected in the token (adjust as needed)
        username = payload.get("email") or payload.get("preferred_username")
        email = payload.get("email")
        first_name = payload.get("given_name", "")
        last_name = payload.get("family_name", "")
        role_names = payload.get("roles") or []  # optional

        if not username or not email:
            raise Unauthorized("Token does not contain enough user information.")

        # Create the local user if missing
        user = self.find_user(username=username)
        if not user:
            # First token role that exists in Superset; if none, "Public".
            role = next((r for r in map(self.find_role, role_names) if r), None) or self.find_role("Public")
            user = self.add_user(
                username=username,
                first_name=first_name,
                last_name=last_name,
                email=email,
                role=role,
            )
            logger.info(f"[CustomJWT] User created: {username}")

        return user
