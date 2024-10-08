import json
from pathlib import Path
import random

from ayon_core.pipeline import (
    AVALON_CONTAINER_ID,
    load,
    get_representation_path,
)

from ayon_resolve.api import lib, constants
from ayon_resolve.api.plugin import get_editorial_publish_data


class LoadEditorialPackage(load.LoaderPlugin):
    """Load editorial package to timeline.

    Loading timeline from OTIO file included media sources
    and timeline structure.
    """

    product_types = {"editorial_pkg"}

    representations = {"*"}
    extensions = {"otio"}

    label = "Load as Timeline"
    order = -10
    icon = "ei.align-left"
    color = "orange"

    def load(self, context, name, namespace, data):
        files = get_representation_path(context["representation"])

        search_folder_path = Path(files).parent / "resources"
        if not search_folder_path.exists():
            search_folder_path = Path(files).parent

        project = lib.get_current_project()
        media_pool = project.GetMediaPool()
        folder_path = context["folder"]["path"]

        # create versioned bin for editorial package
        version_name = context["version"]["name"]
        loaded_bin = lib.create_bin(f"{folder_path}/{name}/{version_name}")

        # make timeline unique name based on folder path
        folder_path_name = folder_path.replace("/", "_").lstrip("_")
        loaded_timeline_name = (
            f"{folder_path_name}_{name}_{version_name}_timeline")
        import_options = {
            "timelineName": loaded_timeline_name,
            "importSourceClips": True,
            "sourceClipsPath": search_folder_path.as_posix(),
        }

        # import timeline from otio file
        timeline = media_pool.ImportTimelineFromFile(files, import_options)

        # get timeline media pool item for metadata update
        timeline_media_pool_item = lib.get_timeline_media_pool_item(
            timeline, loaded_bin
        )

        # Update the metadata
        clip_data = self._get_container_data(
            context, data)

        timeline_media_pool_item.SetMetadata(
            constants.AYON_TAG_NAME, json.dumps(clip_data)
        )

        # set clip color based on random choice
        clip_color = self.get_random_clip_color()
        timeline_media_pool_item.SetClipColor(clip_color)

        # TODO: there are two ways to import timeline resources (representation
        #   and resources folder) but Resolve seems to ignore any of this
        #   since it is importing sources automatically. But we might need
        #   to at least set some metadata to those loaded media pool items
        print("Timeline imported: ", timeline)

    def update(self, container, context):
        """Update the container with the latest version."""

        # Get the latest version of the container data
        timeline_media_pool_item = container["_item"]
        clip_data = timeline_media_pool_item.GetMetadata(
            constants.AYON_TAG_NAME)
        clip_data = json.loads(clip_data)

        clip_data["load"] = {}

        # update publish key in publish container data to be False
        if clip_data["publish"]["publish"] is True:
            clip_data["publish"]["publish"] = False

        timeline_media_pool_item.SetMetadata(
            constants.AYON_TAG_NAME, json.dumps(clip_data))

        self.load(
            context,
            context["product"]["name"],
            container["namespace"],
            container
        )

    def _get_container_data(
        self,
        context: dict,
        data: dict
    ) -> dict:
        """Return metadata related to the representation and version."""

        # add additional metadata from the version to imprint AYON knob
        version_entity = context["version"]

        for key in ("_item", "name"):
            data.pop(key, None)  # remove unnecessary key from the data if it exists

        data = {
            "load": data,
        }

        # add version attributes to the load data
        data["load"].update(
            version_entity["attrib"]
        )

        # add variables related to version context
        data["load"].update(
            {
                "schema": "ayon:container-3.0",
                "id": AVALON_CONTAINER_ID,
                "loader": str(self.__class__.__name__),
                "author": version_entity["data"]["author"],
                "representation": context["representation"]["id"],
                "version": version_entity["version"],
            }
        )

        # add publish data for streamline publishing
        data["publish"] = get_editorial_publish_data(
            folder_path=context["folder"]["path"],
            product_name=context["product"]["name"],
            version=version_entity["version"],
            task=context["representation"]["context"].get("task", {}).get(
                "name"),
        )

        return data

    def get_random_clip_color(self):
        """Return clip color."""

        # list of all available davinci resolve clip colors
        colors = [
            "Orange",
            "Apricot"
            "Yellow",
            "Lime",
            "Olive",
            "Green",
            "Teal",
            "Navy",
            "Blue",
            "Purple",
            "Violet",
            "Pink",
            "Tan",
            "Beige",
            "Brown",
            "Chocolate",
        ]

        # return one of the colors based on random position
        return random.choice(colors)
