import json
from copy import deepcopy

from ayon_core.pipeline.create import CreatorError, CreatedInstance

from ayon_resolve.api import lib, constants
from ayon_resolve.api.plugin import ResolveCreator, get_editorial_publish_data


class CreateEditorialPackage(ResolveCreator):
    """Create Editorial Package."""

    identifier = "io.ayon.creators.resolve.editorial_pkg"
    label = "Editorial Package"
    product_type = "editorial_pkg"
    icon = "camera"
    defaults = ["Main"]

    def create(self, product_name, instance_data, pre_create_data):
        """Create a new editorial_pkg instance.

        Args:
            product_name (str): The product name
            instance_data (dict): The instance data.
            pre_create_data (dict): The pre_create context data.
        """
        super().create(product_name,
                       instance_data,
                       pre_create_data)

        current_timeline = lib.get_current_timeline()

        if not current_timeline:
            raise CreatorError("Make sure to have an active current timeline.")

        timeline_media_pool_item = lib.get_timeline_media_pool_item(
            current_timeline
        )

        tag_metadata = {
            "publish": deepcopy(instance_data),
        }
        tag_metadata["publish"].update(
            get_editorial_publish_data(
                folder_path=instance_data["folderPath"],
                product_name=product_name
            )
        )
        tag_metadata["publish"]["label"] = current_timeline.GetName()

        timeline_media_pool_item.SetMetadata(
            constants.AYON_TAG_NAME, json.dumps(tag_metadata)
        )

        new_instance = CreatedInstance(
            self.product_type,
            product_name,
            tag_metadata["publish"],
            self,
        )
        new_instance.transient_data["timeline_pool_item"] = (
            timeline_media_pool_item)
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
                    "Failed to parse json data from media pool item: %s",
                    media_pool_item.GetName()
                )
                continue

            # exclude all which are not productType editorial_pkg
            if (
                data.get("publish", {}).get("productType") != self.product_type
            ):
                continue

            publish_data = data["publish"]

            # add label into instance data in case it is missing in publish
            # data (legacy publish) or timeline was renamed.
            publish_data["label"] = media_pool_item.GetName()

            # TODO: backward compatibility for legacy workflow instances
            # add variant into instance data in case it is missing in publish
            # data
            if "variant" not in publish_data:
                product_name = publish_data["productName"]
                product_type = publish_data["productType"]
                publish_data["variant"] = product_name.split(product_type)[1]

            current_instance = CreatedInstance(
                self.product_type,
                publish_data["productName"],
                publish_data,
                self
            )

            current_instance.transient_data["timeline_pool_item"] = (
                media_pool_item)
            self._add_instance_to_context(current_instance)

    def update_instances(self, update_list):
        """Store changes of existing instances so they can be recollected.

        Args:
            update_list(List[UpdateData]): Gets list of tuples. Each item
                contain changed instance and it's changes.
        """

        for created_inst, _changes in update_list:
            media_pool_item = created_inst.transient_data[
                "timeline_pool_item"]
            data = media_pool_item.GetMetadata(constants.AYON_TAG_NAME)
            data = json.loads(data)

            data["publish"].update(created_inst.data_to_store())

            media_pool_item.SetMetadata(
                constants.AYON_TAG_NAME,
                json.dumps(data),
            )

    def remove_instances(self, instances):
        """Remove instance marker from track item.

        Args:
            instance(List[CreatedInstance]): Instance objects which should be
                removed.
        """
        for instance in instances:
            self._remove_instance_from_context(instance)
            media_pool_item = instance.transient_data["timeline_pool_item"]

            data = media_pool_item.GetMetadata(constants.AYON_TAG_NAME)
            data = json.loads(data)

            # only removing publishing data since loading data has to remain
            data["publish"] = {}

            media_pool_item.SetMetadata(
                constants.AYON_TAG_NAME,
                json.dumps(data),
            )
