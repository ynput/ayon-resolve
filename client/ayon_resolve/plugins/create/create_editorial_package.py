import json
from copy import deepcopy

from ayon_core.pipeline.create import CreatorError, CreatedInstance

from ayon_resolve.api import lib, constants
from ayon_resolve.api.plugin import ResolveCreator, get_editorial_publish_data


class CreateEditorialPackage(ResolveCreator):
    """Create Editorial Package."""

    identifier = "io.ayon.creators.resolve.editorial_pkg"
    product_name = "editorial_pkgMain"
    label = "Editorial Package"
    product_type = "editorial_pkg"
    icon = "camera"
    defaults = ["Main"]

    def create(self, subset_name, instance_data, pre_create_data):
        """
        """
        super(CreateEditorialPackage, self).create(subset_name,
                                           instance_data,
                                           pre_create_data)

        current_timeline = lib.get_current_timeline()

        if not current_timeline:
            raise CreatorError("Make sure to have an active current timeline.")

        timeline_media_pool_item = lib.get_timeline_media_pool_item(
            current_timeline
        )

        publish_data = deepcopy(instance_data)

        # add publish data for streamline publishing
        publish_data["publish"] = get_editorial_publish_data(
            folder_path=instance_data["folderPath"],
            product_name=self.product_name,
        )

        publish_data["label"] = current_timeline.GetName()
        timeline_media_pool_item.SetMetadata(
            constants.AYON_TAG_NAME, json.dumps(publish_data)
        )

        publish_data["media_pool_item_id"] = timeline_media_pool_item.GetUniqueId()
        new_instance = CreatedInstance(
            self.product_type,
            self.product_name,
            publish_data,
            self,
        )
        new_instance.transient_data["timeline_item"] = timeline_media_pool_item
        self._add_instance_to_context(new_instance)

    def collect_instances(self):
        """Collect all created instances from current timeline."""
        for media_pool_item in lib.iter_all_media_pool_clips():
            data = media_pool_item.GetMetadata(constants.AYON_TAG_NAME)
            if not data:
                continue

            try:
                data = json.loads(data)
            except json.JSONDecodeError:
                self.log.warning(
                    f"Failed to parse json data from media pool item: "
                    f"{media_pool_item.GetName()}"
                )
                continue

            # exclude all which are not productType editorial_pkg
            if (
                data.get("publish", {}).get("productType") != "editorial_pkg"
            ):
                continue

            data["media_pool_item_id"] = media_pool_item.GetUniqueId()
            current_instance = CreatedInstance(
                self.product_type,
                self.product_name,
                data,
                self
            )

            current_instance.transient_data["timeline_item"] = media_pool_item            
            self._add_instance_to_context(current_instance)

    def update_instances(self, update_list):
        """Store changes of existing instances so they can be recollected.

        Args:
            update_list(List[UpdateData]): Gets list of tuples. Each item
                contain changed instance and it's changes.
        """
        for created_inst, _changes in update_list:
            timeline_media_pool_item = created_inst.transient_data["timeline_item"]
            timeline_media_pool_item.SetMetadata(
                constants.AYON_TAG_NAME,
                json.dumps(created_inst.data_to_store()),
            )

    def remove_instances(self, instances):
        """Remove instance marker from track item.

        Args:
            instance(List[CreatedInstance]): Instance objects which should be
                removed.
        """
        for instance in instances:
            self._remove_instance_from_context(instance)
            timeline_media_pool_item = instance.transient_data["timeline_item"]
            timeline_media_pool_item.SetMetadata(
                constants.AYON_TAG_NAME,
                json.dumps({}),
            )

