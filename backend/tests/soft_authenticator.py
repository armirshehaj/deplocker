"""A minimal WebAuthn authenticator, so passkey tests exercise real verification.

It produces the attestation and assertion structures a browser would hand the
API — `fmt: "none"` attestation over an ES256 key — which keeps the signature,
challenge and RP ID checks inside `webauthn` live in the tests instead of mocked.
"""

import hashlib
import json
import os
import struct
from typing import Any

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from webauthn.helpers import bytes_to_base64url, encode_cbor

# User present, user verified, attested credential data included.
_FLAG_UP = 0x01
_FLAG_UV = 0x04
_FLAG_AT = 0x40

_AAGUID = b"\x00" * 16


class SoftAuthenticator:
    def __init__(self, rp_id: str, origin: str) -> None:
        self.rp_id = rp_id
        self.origin = origin
        self.credential_id = os.urandom(32)
        self.sign_count = 0
        self._private_key = ec.generate_private_key(ec.SECP256R1())

    def _client_data(self, ceremony: str, challenge: str) -> bytes:
        return json.dumps(
            {
                "type": ceremony,
                "challenge": challenge,
                "origin": self.origin,
                "crossOrigin": False,
            }
        ).encode()

    def _authenticator_data(self, flags: int, attested: bytes = b"") -> bytes:
        return (
            hashlib.sha256(self.rp_id.encode()).digest()
            + struct.pack(">B", flags)
            + struct.pack(">I", self.sign_count)
            + attested
        )

    def _cose_public_key(self) -> bytes:
        numbers = self._private_key.public_key().public_numbers()
        return encode_cbor(
            {
                1: 2,  # kty: EC2
                3: -7,  # alg: ES256
                -1: 1,  # crv: P-256
                -2: numbers.x.to_bytes(32, "big"),
                -3: numbers.y.to_bytes(32, "big"),
            }
        )

    def create(self, options: dict[str, Any]) -> dict[str, Any]:
        client_data = self._client_data("webauthn.create", options["challenge"])
        attested_credential_data = (
            _AAGUID
            + struct.pack(">H", len(self.credential_id))
            + self.credential_id
            + self._cose_public_key()
        )
        attestation_object = encode_cbor(
            {
                "fmt": "none",
                "attStmt": {},
                "authData": self._authenticator_data(
                    _FLAG_UP | _FLAG_UV | _FLAG_AT, attested_credential_data
                ),
            }
        )

        return {
            "id": bytes_to_base64url(self.credential_id),
            "rawId": bytes_to_base64url(self.credential_id),
            "type": "public-key",
            "authenticatorAttachment": "platform",
            "response": {
                "clientDataJSON": bytes_to_base64url(client_data),
                "attestationObject": bytes_to_base64url(attestation_object),
                "transports": ["internal", "hybrid"],
            },
        }

    def get(self, options: dict[str, Any], user_handle: str = "1") -> dict[str, Any]:
        self.sign_count += 1

        client_data = self._client_data("webauthn.get", options["challenge"])
        authenticator_data = self._authenticator_data(_FLAG_UP | _FLAG_UV)
        signature = self._private_key.sign(
            authenticator_data + hashlib.sha256(client_data).digest(),
            ec.ECDSA(hashes.SHA256()),
        )

        return {
            "id": bytes_to_base64url(self.credential_id),
            "rawId": bytes_to_base64url(self.credential_id),
            "type": "public-key",
            "response": {
                "clientDataJSON": bytes_to_base64url(client_data),
                "authenticatorData": bytes_to_base64url(authenticator_data),
                "signature": bytes_to_base64url(signature),
                "userHandle": bytes_to_base64url(user_handle.encode()),
            },
        }
