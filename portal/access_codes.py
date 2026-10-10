import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings


def _cipher():
    key = hashlib.sha256(settings.SECRET_KEY.encode('utf-8')).digest()
    return Fernet(base64.urlsafe_b64encode(key))


def encrypt_access_code(value):
    return _cipher().encrypt(value.encode('utf-8')).decode('ascii')


def decrypt_access_code(value):
    try:
        return _cipher().decrypt(value.encode('ascii')).decode('utf-8')
    except (InvalidToken, UnicodeDecodeError, ValueError):
        return None
