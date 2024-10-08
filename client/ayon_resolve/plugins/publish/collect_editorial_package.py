import pyblish.api

import ayon_api


class EditorialPackageInstances(pyblish.api.InstancePlugin):
    """Collect all Track items selection."""

    order = pyblish.api.CollectorOrder - 0.49
    label = "Collect Editorial Package Instances"
    families = ["editorial_pkg"]

    def process(self, instance):
        project_name = instance.context.data["projectName"]
        self.log.info(f"project: {project_name}")

        media_pool_item = instance.data["transientData"]["timeline_pool_item"]

        # Special case for versioning editorial_pkg products:
        # * instance created by creator: version up as usual
        # * instance created from loader: loaded version is added 
        #   into the instance by loader. Then version up from initial pkg
        #   to keep 'chained' version across tasks/product when possible.
        version = instance.data.get("version")
        if version is not None:
            # get version from publish data and rise it one up
            version += 1

            # make sure last version of product is higher than current
            # expected current version from publish data
            folder_entity = ayon_api.get_folder_by_path(
                project_name=project_name,
                folder_path=instance.data["folderPath"],
            )
            last_version = ayon_api.get_last_version_by_product_name(
                project_name=project_name,
                product_name=instance.data["productName"],
                folder_id=folder_entity["id"],
            )
            if last_version is not None:
                last_version = int(last_version["version"])
                if version <= last_version:
                    version = last_version + 1

            instance.data["version"] = version

        instance.data.update(
            {
                "mediaPoolItem": media_pool_item,
                "item": media_pool_item,
            }
        )

        self.log.debug(f"Editorial Package: {instance.data}")
