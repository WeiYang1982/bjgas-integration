"""Config flow for bj_gas integration."""

from typing import Any

import probatio

# Eagerly import probatio.codecs to avoid blocking import_module call in event loop.
import probatio.codecs

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .auth import AuthFailed, CannotConnect, get_gas_accounts, login
from .const import DOMAIN


def _normalize_account(account: dict) -> dict:
    """Normalize API account dict to snake_case keys."""
    return {
        "user_code": account["userCode"],
        "label": account.get("label", ""),
        "meter_type": account.get("meterType", ""),
    }


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Returns list of gas accounts on success.
    """
    session = async_get_clientsession(hass)
    phone = data["phone"]
    password = data["password"]

    token = await login(session, phone, password)
    accounts = await get_gas_accounts(session, token)

    return {"token": token, "accounts": accounts}


class BjGasConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for bj_gas."""

    VERSION = 2
    MINOR_VERSION = 0

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._phone: str = ""
        self._password: str = ""
        self._token: str = ""
        self._accounts: list[dict] = []

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step: collect phone and password."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Check for duplicate phone
            await self.async_set_unique_id(user_input["phone"])
            self._abort_if_unique_id_configured()

            try:
                info = await validate_input(self.hass, user_input)
            except AuthFailed:
                errors["base"] = "invalid_auth"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            else:
                self._phone = user_input["phone"]
                self._password = user_input["password"]
                self._token = info["token"]
                self._accounts = info["accounts"]
                return await self.async_step_confirm_accounts()

        return self.async_show_form(
            step_id="user",
            data_schema=probatio.Schema(
                {
                    probatio.Required("phone"): str,
                    probatio.Required("password"): str,
                }
            ),
            errors=errors,
        )

    async def async_step_confirm_accounts(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm discovered gas accounts."""
        errors: dict[str, str] = {}

        if user_input is not None:
            selected = user_input.get("accounts", [])
            if not selected:
                errors["base"] = "no_accounts"
            else:
                selected_set = set(selected)
                accounts = [
                    _normalize_account(a)
                    for a in self._accounts
                    if a["userCode"] in selected_set
                ]
                return self.async_create_entry(
                    title=f"北京燃气 ({self._phone})",
                    data={
                        "phone": self._phone,
                        "password": self._password,
                        "token": self._token,
                        "accounts": accounts,
                    },
                )

        # Build selector options: userCode -> "label (userCode)"
        options = {
            acc["userCode"]: acc.get("label") or acc["userCode"]
            for acc in self._accounts
        }
        default_selected = list(options.keys())

        return self.async_show_form(
            step_id="confirm_accounts",
            data_schema=probatio.Schema(
                {
                    probatio.Required("accounts", default=default_selected): cv.multi_select(
                        options
                    ),
                }
            ),
            description_placeholders={
                "count": str(len(self._accounts)),
            },
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: dict[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauthentication request."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reauthentication form."""
        errors: dict[str, str] = {}
        entry = self._get_reauth_entry()

        if user_input is not None:
            password = user_input["password"]
            phone = entry.data["phone"]
            new_data = {**entry.data, "password": password}

            try:
                info = await validate_input(
                    self.hass, {"phone": phone, "password": password}
                )
            except AuthFailed:
                errors["base"] = "invalid_auth"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            else:
                new_data["token"] = info["token"]
                new_data["accounts"] = [
                    _normalize_account(a) for a in info["accounts"]
                ]
                return self.async_update_reload_and_abort(entry, data=new_data)

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=probatio.Schema(
                {
                    probatio.Required("password"): str,
                }
            ),
            description_placeholders={
                "phone": entry.data["phone"],
            },
            errors=errors,
        )
