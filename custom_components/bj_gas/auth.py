"""Authentication helpers for bj_gas."""

import base64
import urllib.parse

import aiohttp
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding

from .const import (
    CLIENT_ID,
    CLIENT_SECRET,
    GAS_LIST_URL,
    LOGGER,
    LOGIN_URL,
    RSA_PUBLIC_KEY,
    USER_AGENT,
    USER_INFO_URL,
)

_AUTH_EXCEPTIONS = (aiohttp.ClientError, TimeoutError, OSError)


class AuthFailed(Exception):
    """Authentication failed."""


class CannotConnect(Exception):
    """Cannot connect to server."""


def _encrypt_rsa(plaintext: str) -> str:
    """RSA encrypt plaintext with PKCS1v1.5, return base64 string."""
    public_key = serialization.load_pem_public_key(RSA_PUBLIC_KEY.encode())
    ciphertext = public_key.encrypt(plaintext.encode("utf-8"), padding.PKCS1v15())
    return base64.b64encode(ciphertext).decode("utf-8")


async def login(session: aiohttp.ClientSession, phone: str, password: str) -> str:
    """Login with phone + password, return access_token."""
    enc_phone = urllib.parse.quote(_encrypt_rsa(phone), safe="")
    enc_pw = urllib.parse.quote(_encrypt_rsa(password), safe="")

    body = f"grant_type=password&username={enc_phone}&password={enc_pw}"
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": USER_AGENT,
    }

    try:
        async with session.post(
            LOGIN_URL,
            data=body,
            headers=headers,
            auth=aiohttp.BasicAuth(CLIENT_ID, CLIENT_SECRET),
            timeout=aiohttp.ClientTimeout(total=15),
        ) as resp:
            result = await resp.json(content_type=None)
            if resp.status != 200:
                LOGGER.error("Login failed (status %s): %s", resp.status, result)
                raise AuthFailed
            return result["access_token"]
    except _AUTH_EXCEPTIONS as exc:
        LOGGER.error("Login request error: %s", exc)
        raise CannotConnect from exc


async def get_user_id(session: aiohttp.ClientSession, token: str) -> str:
    """Get userId from access_token."""
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json, text/plain, */*",
        "User-Agent": USER_AGENT,
    }
    url = f"{USER_INFO_URL}/{token}"
    try:
        async with session.get(
            url, headers=headers, timeout=aiohttp.ClientTimeout(total=15)
        ) as resp:
            result = await resp.json(content_type=None)
            if resp.status != 200 or not result.get("success"):
                LOGGER.error("GetUserId failed (status %s): %s", resp.status, result)
                raise AuthFailed
            return result["rows"][0]["userId"]
    except _AUTH_EXCEPTIONS as exc:
        LOGGER.error("GetUserId request error: %s", exc)
        raise CannotConnect from exc


async def get_gas_accounts(session: aiohttp.ClientSession, token: str) -> list[dict]:
    """Get all gas accounts for the logged-in user."""
    user_id = await get_user_id(session, token)

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json, text/plain, */*",
        "User-Agent": USER_AGENT,
    }
    url = f"{GAS_LIST_URL}/{user_id}"
    try:
        async with session.get(
            url, headers=headers, timeout=aiohttp.ClientTimeout(total=15)
        ) as resp:
            result = await resp.json(content_type=None)
            if resp.status != 200 or not result.get("success"):
                LOGGER.error(
                    "GetGasAccounts failed (status %s): %s", resp.status, result
                )
                raise AuthFailed
            accounts = result.get("rows", [])
            if not accounts:
                LOGGER.error("No gas accounts found for user %s", user_id)
                raise AuthFailed
            return accounts
    except _AUTH_EXCEPTIONS as exc:
        LOGGER.error("GetGasAccounts request error: %s", exc)
        raise CannotConnect from exc
