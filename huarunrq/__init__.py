"""HuaRunRQ integration."""
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

DOMAIN = "huarunrq"
PLATFORMS = ["sensor"]  # 统一管理需要加载的平台


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the HuaRunRQ component from YAML config (if any)."""
    # 初始化集成数据存储（用于共享API客户端、状态等）
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry):
    """Set up HuaRunRQ from a config entry."""
    # 将配置条目ID存入集成数据，便于后续关联
    hass.data[DOMAIN][config_entry.entry_id] = {}

    # 加载所有关联平台（如sensor）
    success = await hass.config_entries.async_forward_entry_setups(
        config_entry, PLATFORMS
    )

    if not success:
        # 若平台加载失败，清理已存储的数据
        hass.data[DOMAIN].pop(config_entry.entry_id, None)
        return False

    # 监听配置条目更新事件（如选项修改后重新加载）
    config_entry.async_on_unload(
        config_entry.add_update_listener(async_update_options)
    )
    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry):
    """Unload a config entry."""
    # 卸载所有平台
    unloaded = await hass.config_entries.async_forward_entry_unload(
        config_entry, PLATFORMS
    )
    if unloaded:
        # 卸载成功后清理集成数据
        hass.data[DOMAIN].pop(config_entry.entry_id, None)
    return unloaded


async def async_update_options(hass: HomeAssistant, config_entry: ConfigEntry):
    """Handle options update (如用户修改选项后重新加载集成)."""
    await hass.config_entries.async_reload(config_entry.entry_id)
