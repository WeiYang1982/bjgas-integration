"""Constants for the 北京燃气信息查询 integration."""

from datetime import timedelta
import logging

DOMAIN = "bj_gas"
LOGGER = logging.getLogger(__package__)
UPDATE_INTERVAL = timedelta(minutes=10)

# API
BASE_URL = "https://zt.bjgas.com/bjgas-server"
LOGIN_URL = f"{BASE_URL}/oauth/token"
GAS_LIST_URL = f"{BASE_URL}/i/api/nsgetUserGasListEncrypt"
USER_INFO_URL = f"{BASE_URL}/i/api/getUserId"

# OAuth2 credentials
CLIENT_ID = "a8117f61-0643-43ba-a172-bca68f497051"
CLIENT_SECRET = "a376a615-1ba6-453f-8e30-f68ae0b1b3f9"

# RSA public key for encrypting username/password
RSA_PUBLIC_KEY = """-----BEGIN PUBLIC KEY-----
MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQCUzSD3msUGvBK46QQLlPVkMxBJbAzW
OOe22/DrnLYao6t/JcKWu1hfHz3jEQ/ZQ05FD8ifzutNyWao5H7h7UY0Z7rUXRGQ5cvi
XyzGfelLxTDTkNaEsx+7O1rw0t72Is6IE9pWhAMEeH5nGKjK6sn80oUVlz1nSznHZZDH
wfRSMQIDAQAB
-----END PUBLIC KEY-----"""

# Data API
WEEK_QRY_URL = f"{BASE_URL}/i/api/intelligent/getWeekQry?userCode="
STEP_QRY_URL = f"{BASE_URL}/r/api?sysName=CCB&apiName=CM-MOB-IF07"
YEAR_QRY_URL = f"{BASE_URL}/i/api/intelligent/getYearQry?userCode="
USER_INFO_QRY_URL = f"{BASE_URL}/i/api/intelligent/queryUserInfo?userCode="

USER_AGENT = "BeijingGas/2.10.4 (iPhone; iOS 17.0)"
