"""Config flow for HuaRunRQ integration."""
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback

DOMAIN = 'huarunrq'

@config_entries.HANDLERS.register(DOMAIN)
class HuaRunRQFlowHandler(config_entries.ConfigFlow):
    """Handle a config flow for HuaRunRQ."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return HuaRunRQOptionsFlowHandler(config_entry)

    async def async_step_user(self, user_input=None):
        """初始添加集成的表单"""
        errors = {}
        if user_input is not None:
            if not user_input.get('cno'):
                errors['cno'] = 'missing_cno'
            else:
                await self.async_set_unique_id(user_input['cno'])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"华润燃气 ({user_input['cno']})",
                    data={'cno': user_input['cno']},
                    options={'update_interval_hours': 24}  # 默认24小时
                )

        return self.async_show_form(
            step_id='user',
            data_schema=vol.Schema({
                vol.Required('cno', description={'name': '华润燃气编号'}): str
            }),
            errors=errors
        )

class HuaRunRQOptionsFlowHandler(config_entries.OptionsFlow):
    """处理选项设置（使用数字输入框而非滑块）"""

    def __init__(self, config_entry):
        super().__init__()
        self._config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """选项设置页面（使用数字输入框）"""
        errors = {}
        if user_input is not None:
            if not user_input.get('cno'):
                errors['cno'] = 'missing_cno'
                
            # 验证更新间隔输入
            update_str = user_input.get('update_interval_hours', '')
            if not update_str.isdigit():
                errors['update_interval_hours'] = 'invalid_number'
            else:
                update_hours = int(update_str)
                if update_hours < 1 or update_hours > 72:
                    errors['update_interval_hours'] = 'invalid_interval'
                    
            if not errors:
                return self.async_create_entry(title="", data=user_input)

        config_entry = self.hass.config_entries.async_get_entry(self._config_entry.entry_id)
        current_cno = config_entry.options.get('cno', config_entry.data.get('cno'))
        current_interval = config_entry.options.get('update_interval_hours', 24)

        return self.async_show_form(
            step_id='init',
            data_schema=vol.Schema({
                vol.Required('cno', default=current_cno, description={'name': '华润燃气编号'}): str,
                vol.Optional(
                    'update_interval_hours',
                    default=str(current_interval),  # 默认值转为字符串
                    description={'name': '更新数据时间（单位：小时）'}
                ): str  # 使用字符串输入
            }),
            errors=errors
        )
