"""Sensor platform for bj_gas."""

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNKNOWN, UnitOfElectricPotential, UnitOfVolume
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import DOMAIN

GAS_SENSORS: dict[str, dict] = {
    "balance": {
        "name": "燃气费余额",
        "icon": "hass:cash-100",
        "unit_of_measurement": "元",
        "attributes": ["last_update"],
    },
    "current_level": {
        "name": "当前燃气梯",
        "icon": "hass:stairs",
    },
    "current_price": {
        "name": "当前气价",
        "icon": "hass:cash-100",
        "unit_of_measurement": "元/m³",
    },
    "current_level_remain": {
        "name": "当前阶梯剩余额度",
        "device_class": SensorDeviceClass.GAS,
        "unit_of_measurement": UnitOfVolume.CUBIC_METERS,
    },
    "year_consume": {
        "name": "本年度用气量",
        "device_class": SensorDeviceClass.GAS,
        "state_class": SensorStateClass.TOTAL_INCREASING,
        "unit_of_measurement": UnitOfVolume.CUBIC_METERS,
    },
    "month_reg_qty": {
        "name": "当月用气量",
        "device_class": SensorDeviceClass.GAS,
        "state_class": SensorStateClass.TOTAL,
        "unit_of_measurement": UnitOfVolume.CUBIC_METERS,
    },
    "battery_voltage": {
        "name": "气表电量",
        "device_class": SensorDeviceClass.GAS,
        "unit_of_measurement": UnitOfElectricPotential.VOLT,
    },
    "mtr_status": {
        "name": "阀门状态",
        "device_class": SensorDeviceClass.GAS,
        "unit_of_measurement": "",
    },
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities,
) -> None:
    """Set up sensor platform from a config entry."""
    accounts: list[dict] = config_entry.data["accounts"]
    coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]

    sensors: list[SensorEntity] = []
    data = coordinator.data

    for account in accounts:
        user_code = account["user_code"]
        user_data = data.get(user_code, {}) if data else {}

        sensors.extend(
            GASSensor(coordinator, account, key) for key in GAS_SENSORS if key in user_data
        )


        if user_data.get("monthly_bills"):
            sensors.append(GASMonthlyHistorySensor(coordinator, account))
        if user_data.get("daily_bills"):
            sensors.append(GASDailyHistorySensor(coordinator, account))

    async_add_entities(sensors, update_before_add=True)


class GASBaseSensor(CoordinatorEntity, SensorEntity):
    """Base class for bj_gas sensors."""

    _attr_should_poll = False

    def __init__(self, coordinator: DataUpdateCoordinator, account: dict) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._account = account
        self._user_code = account["user_code"]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._user_code)},
            name=account.get("label") or self._user_code,
            manufacturer="北京燃气",
            model=account.get("meter_type"),
        )

    def _user_data(self) -> dict:
        return self.coordinator.data.get(self._user_code, {})


class GASSensor(GASBaseSensor):
    """Representation of a bj_gas sensor."""

    def __init__(
        self, coordinator: DataUpdateCoordinator, account: dict, sensor_key: str
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, account)
        self._sensor_key = sensor_key
        self._config = GAS_SENSORS[sensor_key]
        self._attr_unique_id = f"{DOMAIN}.{self._user_code}_{sensor_key}"
        self._attr_name = self._config.get("name")
        self._attr_icon = self._config.get("icon")
        self._attr_native_unit_of_measurement = self._config.get("unit_of_measurement")
        if "device_class" in self._config:
            self._attr_device_class = self._config["device_class"]
        if "state_class" in self._config:
            self._attr_state_class = self._config["state_class"]
        self._attributes = self._config.get("attributes")

    def get_value(self, attribute: str | None = None):
        """Get the value from coordinator data."""
        try:
            if attribute is None:
                return self._user_data().get(self._sensor_key)
            return self._user_data().get(attribute)
        except KeyError:
            return STATE_UNKNOWN

    @property
    def state(self):
        """Return the state of the sensor."""
        return self.get_value()

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        attributes = {}
        if self._attributes is not None:
            try:
                for attribute in self._attributes:
                    attributes[attribute] = self.get_value(attribute)
            except KeyError:
                pass
        return attributes


class GASMonthlyHistorySensor(GASBaseSensor):
    """Representation of a monthly bill history sensor."""

    def __init__(self, coordinator: DataUpdateCoordinator, account: dict) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, account)
        self._attr_unique_id = f"{DOMAIN}.{self._user_code}_monthly_history"
        self._attr_name = "燃气月账单"
        self._attr_icon = "hass:calendar-month"
        self._attr_device_class = SensorDeviceClass.GAS
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        self._attr_native_unit_of_measurement = UnitOfVolume.CUBIC_METERS

    @property
    def state(self):
        """Return the state of the sensor."""
        bills = self._user_data().get("monthly_bills")
        if not bills:
            return STATE_UNKNOWN
        return bills[0].get("regQty", STATE_UNKNOWN)

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        bills = self._user_data().get("monthly_bills", [])
        return {
            "bills": [
                {
                    "month": entry.get("mon"),
                    "quantity": entry.get("regQty"),
                    "amount": entry.get("amt"),
                }
                for entry in bills
            ]
        }


class GASDailyHistorySensor(GASBaseSensor):
    """Representation of a daily bill history sensor."""

    def __init__(self, coordinator: DataUpdateCoordinator, account: dict) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, account)
        self._attr_unique_id = f"{DOMAIN}.{self._user_code}_daily_history"
        self._attr_name = "燃气日账单"
        self._attr_icon = "hass:calendar"
        self._attr_device_class = SensorDeviceClass.GAS
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        self._attr_native_unit_of_measurement = UnitOfVolume.CUBIC_METERS

    @property
    def state(self):
        """Return the state of the sensor."""
        bills = self._user_data().get("daily_bills")
        if not bills:
            return STATE_UNKNOWN
        return bills[0].get("regQty", STATE_UNKNOWN)

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        bills = self._user_data().get("daily_bills", [])
        return {
            "bills": [
                {
                    "date": entry.get("day", "")[:10],
                    "quantity": entry.get("regQty"),
                }
                for entry in bills
            ]
        }
