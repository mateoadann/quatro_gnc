import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken
from flask import current_app


def _get_key():
    raw_key = current_app.config.get("ENCRYPTION_KEY")
    if raw_key:
        return raw_key.encode("utf-8")
    secret = current_app.config["SECRET_KEY"].encode("utf-8")
    digest = hashlib.sha256(secret).digest()
    return base64.urlsafe_b64encode(digest)


def encrypt_value(value):
    if not value:
        return None
    fernet = Fernet(_get_key())
    return fernet.encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_value(token):
    if not token:
        return ""
    fernet = Fernet(_get_key())
    try:
        return fernet.decrypt(token.encode("utf-8")).decode("utf-8")
    except InvalidToken:
        return ""
