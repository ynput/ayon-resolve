import json
from ayon_core.pipeline.create.legacy_create import LegacyCreator

from ayon_resolve.api import lib


class CreateEditorialPackage(LegacyCreator):
    """Create Editorial Package."""

    name = "editorial_pkg"
    label = "Editorial Package"
    product_type = "editorial_pkg"
    icon = "camera"
    defaults = ["Main"]

    def process(self):
        """Process the creation of the editorial package."""
        current_timeline = lib.get_current_timeline()

        if not current_timeline:
            raise RuntimeError("Make sure to have an active current timeline.")

        timeline_media_pool_item = lib.get_timeline_media_pool_item(
            current_timeline
        )

        publish_data = {"publish": self.data}

        timeline_media_pool_item.SetMetadata(
            lib.pype_tag_name, json.dumps(publish_data)
        )
