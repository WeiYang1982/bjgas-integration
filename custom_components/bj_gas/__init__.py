"""The 北京燃气信息查询 integration."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .auth import AuthFailed, CannotConnect, login
from .const import DOMAIN, LOGGER, UPDATE_INTERVAL
from .gas import GASData, InvalidData


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up 北京燃气信息查询 from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    accounts: list[dict] = entry.data["accounts"]
    token: str = entry.data["token"]

    session = async_create_clientsession(hass)
    api = GASData(session, token, accounts)

    coordinator = DataUpdateCoordinator(
        hass,
        logger=LOGGER,
        name=DOMAIN,
        update_interval=UPDATE_INTERVAL,
        update_method=api.async_get_data,
    )

    try:
        await coordinator.async_refresh()
    except ConfigEntryAuthFailed:
        LOGGER.warning("初始认证失败，尝试自动重新认证")
        if not await _try_reauth(hass, entry):
            LOGGER.error("自动重新认证失败，需要用户重新配置")
            raise ConfigEntryAuthFailed from None
        # Re-fetch with new token
        token = entry.data["token"]
        api = GASData(session, token, accounts)
        coordinator = DataUpdateCoordinator(
            hass,
            logger=LOGGER,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
            update_method=api.async_get_data,
        )
        try:
            await coordinator.async_refresh()
        except (AuthFailed, CannotConnect, InvalidData) as exc:
            LOGGER.error("重新认证后数据刷新失败: %s", exc)
            raise ConfigEntryNotReady from exc
    except InvalidData as exc:
        LOGGER.warning("初始数据刷新失败: %s", exc)
        raise ConfigEntryNotReady from exc

    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
    }

    await hass.config_entries.async_forward_entry_setups(entry, ["sensor"])

    return True


async def _try_reauth(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Try to re-authenticate using stored phone + password."""
    phone = entry.data.get("phone")
    password = entry.data.get("password")
    if not phone or not password:
        return False

    try:
        session = async_create_clientsession(hass)
        new_token = await login(session, phone, password)
    except (AuthFailed, CannotConnect) as exc:
        LOGGER.error("自动重新认证失败: %s", exc)
        return False

    new_data = {**entry.data, "token": new_token}
    hass.config_entries.async_update_entry(entry, data=new_data)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, ["sensor"])
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
