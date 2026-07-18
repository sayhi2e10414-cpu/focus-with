from __future__ import annotations

import base64
import hashlib
import hmac
import secrets


SCRYPT_N = 2**14
SCRYPT_R = 8
SCRYPT_P = 1
SCRYPT_DKLEN = 32
PBKDF2_ITERATIONS = 600_000


def hash_secret(value: str) -> str:
    """Return a portable scrypt hash suitable for an environment file."""
    if len(value) < 12:
        raise ValueError("The FocusWith admin password must contain at least 12 characters")
    salt = secrets.token_bytes(16)
    if hasattr(hashlib, "scrypt"):
        digest = hashlib.scrypt(
            value.encode("utf-8"),
            salt=salt,
            n=SCRYPT_N,
            r=SCRYPT_R,
            p=SCRYPT_P,
            dklen=SCRYPT_DKLEN,
        )
        fields = ["scrypt", str(SCRYPT_N), str(SCRYPT_R), str(SCRYPT_P)]
    else:  # Some vendor Python builds omit OpenSSL scrypt support.
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            value.encode("utf-8"),
            salt,
            PBKDF2_ITERATIONS,
            dklen=SCRYPT_DKLEN,
        )
        fields = ["pbkdf2-sha256", str(PBKDF2_ITERATIONS)]
    return ":".join(
        [
            *fields,
            base64.urlsafe_b64encode(salt).decode("ascii").rstrip("="),
            base64.urlsafe_b64encode(digest).decode("ascii").rstrip("="),
        ]
    )


def verify_secret(value: str, encoded: str) -> bool:
    try:
        fields = encoded.split(":")
        algorithm = fields[0]
        if algorithm == "scrypt" and len(fields) == 6:
            _, raw_n, raw_r, raw_p, raw_salt, raw_digest = fields
        elif algorithm == "pbkdf2-sha256" and len(fields) == 4:
            _, raw_iterations, raw_salt, raw_digest = fields
        else:
            return False
        salt = base64.urlsafe_b64decode(raw_salt + "=" * (-len(raw_salt) % 4))
        expected = base64.urlsafe_b64decode(raw_digest + "=" * (-len(raw_digest) % 4))
        if algorithm == "scrypt":
            actual = hashlib.scrypt(
                value.encode("utf-8"),
                salt=salt,
                n=int(raw_n),
                r=int(raw_r),
                p=int(raw_p),
                dklen=len(expected),
            )
        else:
            actual = hashlib.pbkdf2_hmac(
                "sha256",
                value.encode("utf-8"),
                salt,
                int(raw_iterations),
                dklen=len(expected),
            )
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError, AttributeError):
        return False


def opaque_hash(value: str) -> str:
    """Hash a high-entropy OAuth artifact before storing it."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
