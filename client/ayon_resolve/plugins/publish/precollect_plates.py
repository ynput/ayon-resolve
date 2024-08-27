import pyblish


class PrecollectPlate(pyblish.api.InstancePlugin):
    """PreCollect new plates."""

    order = pyblish.api.CollectorOrder - 0.48
    label = "Precollect Plate"
    hosts = ["resolve"]
    families = ["plate"]

    def process(self, instance):
        """
        Args:
            instance (pyblish.Instance): The shot instance to update.
        """
        # Temporary disable no-representation failure.
        # TODO not sure what should happen for the plate.
        instance.data["folderPath"] = instance.data.pop("hierarchy_path")
        instance.data["integrate"] = False 
