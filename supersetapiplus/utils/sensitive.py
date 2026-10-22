"""Mascaramento de dados sensíveis (credenciais, tokens e cookies) antes de registrá-los em log."""
import json
import re
from typing import Any, Mapping
from urllib.parse import parse_qsl, urlencode

MASK = "***"

SENSITIVE_HEADERS = frozenset({"authorization", "cookie", "set-cookie", "x-csrftoken", "x-csrf-token"})

SENSITIVE_KEYS = frozenset({
    "password", "passwords", "access_token", "refresh_token", "csrf_token", "token",
    "secret", "encrypted_extra", "masked_encrypted_extra", "ssh_tunnel_passwords",
})

# Senha embutida em URI de conexão (ex.: sqlalchemy_uri "postgresql://user:senha@host/db")
_URI_PASSWORD = re.compile(r"(://[^:/@\s]+:)[^@\s]+(@)")


def _is_sensitive_key(key: Any) -> bool:
    return isinstance(key, str) and key.lower() in SENSITIVE_KEYS


def mask_headers(headers: Mapping[str, Any] | None) -> dict:
    """Cópia dos cabeçalhos com os valores de autenticação substituídos por `***`."""
    return {k: (MASK if k.lower() in SENSITIVE_HEADERS else v) for k, v in (headers or {}).items()}


def mask_data(data: Any) -> Any:
    """Cópia de dict/list com valores de chaves sensíveis mascarados e senhas de URI ocultadas."""
    if isinstance(data, Mapping):
        return {k: (MASK if _is_sensitive_key(k) else mask_data(v)) for k, v in data.items()}
    if isinstance(data, (list, tuple)):
        return [mask_data(v) for v in data]
    if isinstance(data, str):
        return _URI_PASSWORD.sub(rf"\1{MASK}\2", data)
    return data


def mask_body(body: Any) -> Any:
    """Mascara um corpo de requisição/resposta em JSON, form-urlencoded ou estrutura Python."""
    if body is None or isinstance(body, (Mapping, list, tuple)):
        return mask_data(body)
    if isinstance(body, bytes):
        try:
            body = body.decode("utf-8")
        except UnicodeDecodeError:
            return f"<{len(body)} bytes>"
    if not isinstance(body, str):
        return body
    try:
        return json.dumps(mask_data(json.loads(body)), ensure_ascii=False)
    except ValueError:
        pass
    pairs = parse_qsl(body, keep_blank_values=True)
    if pairs and "=" in body and not body.lstrip().startswith("<"):
        return urlencode([(k, MASK if _is_sensitive_key(k) else v) for k, v in pairs])
    return mask_data(body)


def mask_request_kwargs(kwargs: Mapping[str, Any]) -> dict:
    """Cópia dos kwargs de `requests` com cabeçalhos e corpos mascarados, para log."""
    masked = dict(kwargs)
    if "headers" in masked:
        masked["headers"] = mask_headers(masked["headers"])
    for key in ("json", "data", "params"):
        if key in masked:
            masked[key] = mask_body(masked[key])
    if "files" in masked:
        masked["files"] = "<files>"
    return masked
