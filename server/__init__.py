from typing import Type, Any

from ayon_server.addons import BaseServerAddon

from .settings import ResolveSettings, DEFAULT_VALUES
from .conversion import convert_settings_overrides


class ResolveAddon(BaseServerAddon):
    settings_model: Type[ResolveSettings] = ResolveSettings

    async def get_default_settings(self):
        settings_model_cls = self.get_settings_model()
        return settings_model_cls(**DEFAULT_VALUES)
    
    async def convert_settings_overrides(
        self,
        source_version: str,
        overrides: dict[str, Any],
    ) -> dict[str, Any]:
        convert_settings_overrides(source_version, overrides)
        # Use super conversion
        return await super().convert_settings_overrides(
            source_version, overrides
        )
