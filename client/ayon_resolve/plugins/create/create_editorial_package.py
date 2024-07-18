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
        timeline_name = current_timeline.GetName()

        # get timeline media pool item for metadata update
        timeline_media_pool_item = None
        for item in lib.iter_all_media_pool_clips():
            item_name = item.GetName()
            if item_name != timeline_name:
                continue
            timeline_media_pool_item = item
            break

        # Update the metadata
        if timeline_media_pool_item:
            publish_data = {"publish": self.data}
            timeline_media_pool_item.SetMetadata(
                lib.pype_tag_name, json.dumps(publish_data)
            )
        else:
            NameError("Timeline not found in media pool.")
