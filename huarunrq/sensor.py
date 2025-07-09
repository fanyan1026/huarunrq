"""HuaRunRQ 传感器平台逻辑"""
from datetime import timedelta
import logging
import base64
import time
import random
import json
import voluptuous as vol
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.backends import default_backend
from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.const import CONF_NAME
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.util import Throttle
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from . import DOMAIN

_LOGGER = logging.getLogger(__name__)

CONF_CNO = "cno"
CONF_UPDATE_INTERVAL = "update_interval_hours"


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_CNO): vol.Coerce(str),
    vol.Optional(CONF_NAME, default="华润燃气余额"): vol.Coerce(str),
    vol.Optional(CONF_UPDATE_INTERVAL, default=24): vol.All(
        vol.Coerce(int),
        vol.Range(min=1, max=72)
    ),
})


async def async_setup_platform(
    hass: HomeAssistant,
    config: dict,
    add_entities: AddEntitiesCallback,
    discovery_info=None
) -> None:
    cno = config[CONF_CNO]
    name = config[CONF_NAME]
    update_interval = config.get(CONF_UPDATE_INTERVAL, 24)
    _LOGGER.debug("通过YAML配置创建传感器: %s (cno=%s, 更新间隔=%s小时)", 
                 name, cno, update_interval)
    sensor = HuaRunRQSensor(hass, name, cno, entry_id=None, update_interval=update_interval)
    add_entities([sensor], True)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback
) -> None:
    _LOGGER.info("开始设置传感器平台: %s (entry_id=%s)", 
                config_entry.title, config_entry.entry_id)
    
    # 检查依赖
    try:
        import cryptography
        _LOGGER.debug("cryptography库版本: %s", cryptography.__version__)
    except ImportError:
        _LOGGER.error("缺少cryptography库，请安装: pip install cryptography")
        return
    
    # 检查必要配置
    cno = config_entry.data.get(CONF_CNO)
    if not cno:
        _LOGGER.error("配置项 %s 缺少cno参数", config_entry.entry_id)
        return

    name = config_entry.title or "华润燃气余额"
    
    # 关键修复1：将字符串转为整数（处理配置项中的字符串）
    try:
        update_interval = int(config_entry.options.get(CONF_UPDATE_INTERVAL, 24))
    except ValueError:
        _LOGGER.warning("无效的更新间隔，使用默认值24小时")
        update_interval = 24
    
    try:
        sensor = HuaRunRQSensor(
            hass, 
            name, 
            cno, 
            entry_id=config_entry.entry_id,
            update_interval=update_interval  # 确保传入整数
        )
        async_add_entities([sensor], True)
        
        config_entry.async_on_unload(
            config_entry.add_update_listener(update_listener)
        )
        _LOGGER.info("传感器 %s 创建成功（更新间隔: %s小时）", name, update_interval)
        
    except Exception as e:
        _LOGGER.exception("创建传感器失败: %s", str(e))
        return


async def update_listener(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(config_entry.entry_id)


class HuaRunRQSensor(SensorEntity):
    def __init__(
        self, 
        hass: HomeAssistant,
        name: str, 
        cno: str, 
        entry_id: str | None,
        update_interval: int = 24  # 确保参数为整数
    ):
        self.hass = hass
        self._name = name
        self._cno = cno
        self._entry_id = entry_id
        self._state = None
        self._attributes = {}
        
        # 关键修复2：确保更新间隔是整数
        try:
            self._update_interval = int(update_interval)
        except ValueError:
            self._update_interval = 24  # 默认值
            _LOGGER.warning("无效的更新间隔，使用默认值24小时")
        
        # 关键修复3：使用整数创建timedelta
        self._attr_min_time_between_updates = timedelta(hours=self._update_interval)
        self._attr_unique_id = f"huarunrq_{cno}_{entry_id or 'yaml'}"
        
        _LOGGER.debug("初始化传感器: %s（唯一ID: %s, 更新间隔: %s小时）", 
                     name, self._attr_unique_id, self._update_interval)

    @property
    def name(self) -> str:
        return self._name

    @property
    def state(self) -> any:
        return self._state

    @property
    def extra_state_attributes(self) -> dict:
        attrs = {
            "燃气编号": self._cno,
            "更新间隔（小时）": self._update_interval,
            "最后更新时间": self._attributes.get("last_update", "未更新")
        }
        attrs.update({k: v for k, v in self._attributes.items() if k not in attrs})
        return attrs

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._cno)},
            name="华润燃气表",
            manufacturer="华润燃气",
            model="智能燃气表",
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def native_unit_of_measurement(self) -> str:
        return "元"

    @property
    def device_class(self) -> str:
        return "monetary"

    async def async_update(self) -> None:
        _LOGGER.debug("开始更新传感器数据: %s（间隔: %s小时）", 
                     self._name, self._update_interval)
        
        try:
            session = async_get_clientsession(self.hass)
            data = await self._async_fetch_api_data(session)
            self._state = data.get("totalGasBalance")
            self._attributes["last_update"] = time.strftime("%Y-%m-%d %H:%M:%S")
            _LOGGER.info("传感器 %s 更新成功，当前余额: %s元", self._name, self._state)
            
        except Exception as e:
            _LOGGER.exception("传感器 %s 更新失败: %s", self._name, str(e))

    async def _async_fetch_api_data(self, session) -> dict:
        try:
            # 加载公钥
            public_key_pem = '''-----BEGIN PUBLIC KEY-----
MFwwDQYJKoZIhvcNAQEBBQADSwAwSAJBAIi4Gb8iOGcc05iqNilFb1gM6/iG4fSiECeEaEYN2cxaBVT+6zgp+Tp0TbGVqGMIB034BLaVdNZZPnqKFH4As8UCAwEAAQ==
-----END PUBLIC KEY-----'''
            public_key = serialization.load_pem_public_key(
                public_key_pem.encode("utf-8"),
                backend=default_backend()
            )

            # 生成加密参数
            timestamp = int(time.time() * 1000)
            random_num = random.randint(1000, 9999)
            data_to_encrypt = f"e5b871c278a84defa8817d22afc34338#{timestamp}#{random_num}"
            encrypted_data = public_key.encrypt(
                data_to_encrypt.encode("utf-8"),
                padding.PKCS1v15()
            )
            base64_encrypted_data = base64.urlsafe_b64encode(encrypted_data).decode("utf-8")

            # 构建请求
            request_body = {"USER": "bizH5", "PWD": base64_encrypted_data}
            base64_encoded_body = base64.urlsafe_b64encode(
                json.dumps(request_body).encode("utf-8")
            ).decode("utf-8")

            # 调用API
            api_url = f"https://mbhapp.crcgas.com/bizonline/api/h5/pay/queryArrears?authVersion=v2&consNo={self._cno}"
            headers = {"Content-Type": "application/json", "Param": base64_encoded_body}
            
            async with session.get(api_url, headers=headers, timeout=15) as response:
                response_text = await response.text()
                _LOGGER.debug("API原始响应: %s", response_text[:200])
                
                try:
                    result = json.loads(response_text)
                except json.JSONDecodeError:
                    raise ValueError(f"API返回格式错误: {response_text[:200]}")

                if result.get("statusCode") == "B0001" or result.get("msg") == "服务器异常！":
                    _LOGGER.error("API服务器异常，请稍后重试（code: %s）", result.get("statusCode"))
                    raise ConnectionError("服务器异常，无法获取数据")

                if result.get("msg") == "操作成功":
                    return result.get("dataResult", {})
                else:
                    raise ValueError(f"API错误: {result.get('msg')}（code: {result.get('statusCode')}）")

        except Exception as e:
            _LOGGER.exception("API请求过程出错")
            raise

    async def async_will_remove_from_hass(self) -> None:
        _LOGGER.info("传感器 %s（编号: %s）已移除", self._name, self._cno)
