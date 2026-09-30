"""Gas data fetching for bj_gas."""

import asyncio

import aiohttp

from homeassistant.exceptions import ConfigEntryAuthFailed

from .const import (
    LOGGER,
    STEP_QRY_URL,
    USER_AGENT,
    USER_INFO_QRY_URL,
    WEEK_QRY_URL,
    YEAR_QRY_URL,
)


class InvalidData(Exception):
    """Invalid data received."""


class GASData:
    """Fetch gas data for multiple accounts."""

    def __init__(
        self, session: aiohttp.ClientSession, token: str, accounts: list[dict]
    ) -> None:
        """Initialize the data fetcher."""
        self._session = session
        self._token = token
        self._accounts = accounts
        self._info: dict[str, dict] = {}

    def _common_headers(self) -> dict[str, str]:
        return {
            "Host": "zt.bjgas.com",
            "Accept": "application/json, text/plain, */*",
            "X-Requested-With": "XMLHttpRequest",
            "Accept-Language": "zh-cn, zh-Hans; q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "User-Agent": USER_AGENT,
            "Connection": "keep-alive",
            "Authorization": f"Bearer {self._token}",
        }

    async def _get_json(self, url: str, *, method: str = "get", **kwargs) -> dict:
        """Make a request and return JSON, handling auth errors."""
        headers = self._common_headers()
        headers.update(kwargs.pop("headers", {}))
        try:
            if method == "post":
                resp = await self._session.post(
                    url,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10),
                    **kwargs,
                )
            else:
                resp = await self._session.get(
                    url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)
                )
        except (aiohttp.ClientError, TimeoutError, OSError) as exc:
            raise InvalidData(f"Request error: {exc}") from exc

        if resp.status == 401:
            raise ConfigEntryAuthFailed
        if resp.status != 200:
            raise InvalidData(f"Response status_code = {resp.status}")

        return await resp.json(content_type=None)

    async def async_get_week(self, user_code: str) -> None:
        """Fetch weekly bill data."""
        result = await self._get_json(WEEK_QRY_URL + user_code)
        if result["success"]:
            self._info[user_code]["daily_bills"] = result["rows"][0]["infoList"]
        else:
            raise InvalidData(f"async_get_week error: {result}")

    async def async_get_year(self, user_code: str) -> None:
        """Fetch yearly bill data."""
        result = await self._get_json(YEAR_QRY_URL + user_code)
        if result["success"]:
            self._info[user_code]["monthly_bills"] = result["rows"][0]["infoList"]
        else:
            raise InvalidData(f"async_get_year error: {result}")

    async def async_get_userinfo(self, user_code: str) -> None:
        """Fetch user info (balance, price, etc.)."""
        result = await self._get_json(USER_INFO_QRY_URL + user_code)
        if result["success"]:
            data = result["rows"][0]
            self._info[user_code]["last_update"] = data["fiscalDate"]
            self._info[user_code]["balance"] = float(data["remainAmt"])
            self._info[user_code]["battery_voltage"] = float(data["batteryVoltage"])
            self._info[user_code]["current_price"] = float(data["gasPrice"])
            self._info[user_code]["month_reg_qty"] = float(data["regQty"])
            self._info[user_code]["mtr_status"] = data["mtrStatus"]
        else:
            raise InvalidData(f"async_get_userinfo error: {result}")

    async def async_get_step(self, user_code: str) -> None:
        """Fetch step pricing data."""
        headers = {
            "Content-Type": "application/json;charset=UTF-8",
            "Origin": "file://",
        }
        payload = {"CM-MOB-IF07": {"input": {"UniUserCode": user_code}}}
        result = await self._get_json(
            STEP_QRY_URL, method="post", json=payload, headers=headers
        )
        data = result["soapenv:Envelope"]["soapenv:Body"]["CM-MOB-IF07"]["output"]
        if float(data["Step1LeftoverQty"]) > 0:
            self._info[user_code]["current_level"] = 1
            self._info[user_code]["current_level_remain"] = float(
                data["Step1LeftoverQty"]
            )
        else:
            self._info[user_code]["current_level"] = 2
            self._info[user_code]["current_level_remain"] = float(
                data["Step2LeftoverQty"]
            )
        self._info[user_code]["year_consume"] = float(data["TotalSq"])

    async def _fetch_account(self, account: dict) -> None:
        """Fetch all data for a single account."""
        user_code = account["user_code"]
        self._info[user_code] = {}
        tasks = [
            self.async_get_userinfo(user_code),
            self.async_get_week(user_code),
            self.async_get_year(user_code),
            self.async_get_step(user_code),
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for result in results:
            if isinstance(result, ConfigEntryAuthFailed):
                raise result
            if isinstance(result, Exception):
                LOGGER.warning("Error fetching data for %s: %s", user_code, result)

    async def async_get_data(self) -> dict[str, dict]:
        """Fetch data for all accounts, return {user_code: {...}}."""
        self._info = {}
        for account in self._accounts:
            try:
                await self._fetch_account(account)
            except ConfigEntryAuthFailed:
                raise
            except InvalidData as exc:
                LOGGER.error(
                    "Failed to fetch data for %s: %s",
                    account["user_code"],
                    exc,
                )
        LOGGER.debug("Data %s", self._info)
        return self._info
