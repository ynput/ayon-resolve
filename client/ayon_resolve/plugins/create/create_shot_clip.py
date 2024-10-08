import copy

from ayon_resolve.api import plugin, lib, constants
from ayon_resolve.api.lib import (
    get_video_track_names,
    get_current_timeline_items,
    create_bin,
)
from ayon_core.pipeline.create import CreatorError, CreatedInstance
from ayon_core.lib import BoolDef, EnumDef, TextDef, UILabelDef, NumberDef


# Used as a key by the creators in order to 
# retrieve the instances data into clip markers.
_CONTENT_ID = "resolve_sub_products"


# Shot attributes
CLIP_ATTR_DEFS = [
    EnumDef(
        "fps",
        items=[
            {"value": "from_selection", "label": "From selection"},
            {"value": 23.997, "label": "23.976"},
            {"value": 24, "label": "24"},
            {"value": 25, "label": "25"},
            {"value": 29.97, "label": "29.97"},
            {"value": 30, "label": "30"}
        ],
        label="FPS"
    ),
    NumberDef(
        "workfileFrameStart",
        default=1001,
        label="Workfile start frame"
    ),
    NumberDef(
        "handleStart",
        default=0,
        label="Handle start"
    ),
    NumberDef(
        "handleEnd",
        default=0,
        label="Handle end"
    ),
    NumberDef(
        "frameStart",
        default=0,
        label="Frame start",
        disabled=True,
    ),
    NumberDef(
        "frameEnd",
        default=0,
        label="Frame end",
        disabled=True,
    ),
    NumberDef(
        "clipIn",
        default=0,
        label="Clip in",
        disabled=True,
    ),
    NumberDef(
        "clipOut",
        default=0,
        label="Clip out",
        disabled=True,
    ),
    NumberDef(
        "clipDuration",
        default=0,
        label="Clip duration",
        disabled=True,
    ),
    NumberDef(
        "sourceIn",
        default=0,
        label="Media source in",
        disabled=True,
    ),
    NumberDef(
        "sourceOut",
        default=0,
        label="Media source out",
        disabled=True,
    )    
]


class _ResolveInstanceClipCreator(plugin.HiddenResolvePublishCreator):
    """Wrapper class for clip types products.
    """

    def create(self, instance_data, _):
        """Return a new CreateInstance for new shot from Resolve.

        Args:
            instance_data (dict): global data from original instance

        Return:
            CreatedInstance: The created instance object for the new shot.
        """
        instance_data.update({
            "productName": f"{self.product_type}{instance_data['variant']}",
            "productType": self.product_type,
            "has_promised_context": True,
            "newHierarchyIntegration": True,
            # Backwards compatible (Deprecated since 24/06/06)
            "newAssetPublishing": True,            
        })
        instance_data["folder"] = instance_data["folderPath"]

        new_instance = CreatedInstance(
            self.product_type, instance_data["productName"], instance_data, self
        )
        self._add_instance_to_context(new_instance)
        new_instance.transient_data["has_promised_context"] = True
        return new_instance

    def update_instances(self, update_list):
        """Store changes of existing instances so they can be recollected.

        Args:
            update_list(List[UpdateData]): Gets list of tuples. Each item
                contain changed instance and it's changes.
        """
        for created_inst, _changes in update_list:
            track_item = created_inst.transient_data["track_item"]
            tag_data = lib.get_timeline_item_ayon_tag(track_item)            

            try:
                instances_data = tag_data[_CONTENT_ID]

            # Backwards compatible (Deprecated since 24/09/05)
            except KeyError:
                tag_data[_CONTENT_ID] = {}
                instances_data = tag_data[_CONTENT_ID]

            instances_data[self.identifier] = created_inst.data_to_store()
            lib.imprint(track_item, tag_data)

    def remove_instances(self, instances):
        """Remove instance marker from track item.

        Args:
            instance(List[CreatedInstance]): Instance objects which should be
                removed.
        """
        for instance in instances:
            track_item = instance.transient_data["track_item"]
            tag_data = lib.get_timeline_item_ayon_tag(track_item)
            instances_data = tag_data.get(_CONTENT_ID, {})
            instances_data.pop(self.identifier, None)
            self._remove_instance_from_context(instance)

            # Remove markers if deleted all of the instances
            if not instances_data: 
                track_item.DeleteMarkersByColor(constants.AYON_MARKER_COLOR)
                if track_item.GetClipColor() != constants.SELECTED_CLIP_COLOR:
                    track_item.ClearClipColor()

            # Push edited data in marker
            else:
                lib.imprint(track_item, tag_data)


class ResolveShotInstanceCreator(_ResolveInstanceClipCreator):
    """Shot product type creator class"""
    identifier = "io.ayon.creators.resolve.shot"
    product_type = "shot"    
    label = "Editorial Shot"

    def get_instance_attr_defs(self):
        instance_attributes = CLIP_ATTR_DEFS
        return instance_attributes


class _ResolveInstanceClipCreatorBase(_ResolveInstanceClipCreator):
    """ Base clip product creator.
    """

    def get_instance_attr_defs(self):
        gui_tracks = get_video_track_names()
        instance_attributes = [
            TextDef(
                "parentInstance",
                label="Linked to",
                disabled=True,
            )           
        ]
        if self.product_type == "plate":
            instance_attributes.extend([
                BoolDef(
                    "vSyncOn",
                    label="Enable Vertical Sync",
                    tooltip="Switch on if you want clips above "
                            "each other to share its attributes",
                    default=True,
                ),            
                EnumDef(
                    "vSyncTrack",
                    label="Hero Track",
                    tooltip="Select driving track name which should "
                            "be mastering all others",
                    items=gui_tracks or ["<nothing to select>"],
                ), 
            ])

        return instance_attributes


class EditorialPlateInstanceCreator(_ResolveInstanceClipCreatorBase):
    """Plate product type creator class"""
    identifier = "io.ayon.creators.resolve.plate"
    product_type = "plate"
    label = "Editorial Plate"

    def create(self, instance_data, _):
        """Return a new CreateInstance for new shot from Resolve.

        Args:
            instance_data (dict): global data from original instance

        Return:
            CreatedInstance: The created instance object for the new shot.
        """
        if instance_data.get("clip_variant") == "<track_name>":
            instance_data["variant"] = instance_data["hierarchyData"]["track"]

        else:
            instance_data["variant"] = instance_data["clip_variant"]

        return super().create(instance_data, None)


class EditorialAudioInstanceCreator(_ResolveInstanceClipCreatorBase):
    """Audio product type creator class"""
    identifier = "io.ayon.creators.resolve.audio"
    product_type = "audio"
    label = "Editorial Audio"


class CreateShotClip(plugin.ResolveCreator):
    """Publishable clip"""

    identifier = "io.ayon.creators.resolve.clip"
    label = "Create Publishable Clip"
    product_type = "editorial"
    icon = "film"
    defaults = ["Main"]

    detailed_description = """
Publishing clips/plate, audio for new shots to project
or updating already created from Resolve. Publishing will create 
OTIO file.
"""
    create_allow_thumbnail = False

    def get_pre_create_attr_defs(self):

        def header_label(text):
            return f"<br><b>{text}</b>"

        tokens_help = """\nUsable tokens:
    {_clip_}: name of used clip
    {_track_}: name of parent track layer
    {_sequence_}: name of parent sequence (timeline)"""
        gui_tracks = get_video_track_names()

        # Project settings might be applied to this creator via
        # the inherited `Creator.apply_settings`
        presets = self.presets

        return [

            BoolDef("use_selection",
                    label="Use only clips with <b>Chocolate</b>  clip color",
                    tooltip=(
                        "When enabled only clips of Chocolate clip color are "
                        "considered.\n\n"
                        "Acts as a replacement to 'Use selection' because "
                        "Resolves API exposes no functionality to retrieve "
                        "the currently selected timeline items."
                    ),
                    default=True),

            # hierarchyData
            UILabelDef(
                label=header_label("Shot Template Keywords")
            ),
            TextDef(
                "folder",
                label="{folder}",
                tooltip="Name of folder used for root of generated shots.\n"
                        f"{tokens_help}",
                default=presets.get("folder", "shots"),
            ),
            TextDef(
                "episode",
                label="{episode}",
                tooltip=f"Name of episode.\n{tokens_help}",
                default=presets.get("episode", "ep01"),
            ),
            TextDef(
                "sequence",
                label="{sequence}",
                tooltip=f"Name of sequence of shots.\n{tokens_help}",
                default=presets.get("sequence", "sq01"),
            ),
            TextDef(
                "track",
                label="{track}",
                tooltip=f"Name of timeline track.\n{tokens_help}",
                default=presets.get("track", "{_track_}"),
            ),
            TextDef(
                "shot",
                label="{shot}",
                tooltip="Name of shot. '#' is converted to padded number."
                        f"\n{tokens_help}",
                default=presets.get("shot", "sh###"),
            ),

            # renameHierarchy
            UILabelDef(
                label=header_label("Shot Hierarchy and Rename Settings")
            ),
            TextDef(
                "hierarchy",
                label="Shot Parent Hierarchy",
                tooltip="Parents folder for shot root folder, "
                        "Template filled with *Hierarchy Data* section",
                default=presets.get("hierarchy", "{folder}/{sequence}"),
            ),
            BoolDef(
                "clipRename",
                label="Rename Shots/Clips",
                tooltip="Renaming selected clips on fly",
                default=presets.get("clipRename", False),
            ),
            TextDef(
                "clipName",
                label="Rename Template",
                tooltip="template for creating shot names, used for "
                        "renaming (use rename: on)",
                default=presets.get("clipName", "{sequence}{shot}"),
            ),
            NumberDef(
                "countFrom",
                label="Count Sequence from",
                tooltip="Set where the sequence number starts from",
                default=presets.get("countFrom", 10),
            ),
            NumberDef(
                "countSteps",
                label="Stepping Number",
                tooltip="What number is adding every new step",
                default=presets.get("countSteps", 10),
            ),

            # verticalSync
            UILabelDef(
                label=header_label("Vertical Synchronization of Attributes")
            ),
            BoolDef(
                "vSyncOn",
                label="Enable Vertical Sync",
                tooltip="Switch on if you want clips above "
                        "each other to share its attributes",
                default=presets.get("vSyncOn", True),
            ),
            EnumDef(
                "vSyncTrack",
                label="Hero Track",
                tooltip="Select driving track name which should "
                        "be mastering all others",
                items=gui_tracks or ["<nothing to select>"],
            ),

            # publishSettings
            UILabelDef(
                label=header_label("Clip Publish Settings")
            ),
            EnumDef(
                "clip_variant",
                label="Product Variant",
                tooltip="Chosen variant which will be then used for "
                        "product name, if <track_name> "
                        "is selected, name of track layer will be used",
                items=['<track_name>', 'main', 'bg', 'fg', 'bg', 'animatic'],
            ),
            EnumDef(
                "productType",
                label="Product Type",
                tooltip="How the product will be used",
                items=['plate'],  # it is prepared for more types
            ),
            EnumDef(
                "reviewTrack",
                label="Use Review Track",
                tooltip="Generate preview videos on fly, if "
                        "'< none >' is defined nothing will be generated.",
                items=['< none >'] + gui_tracks,
            ),
            BoolDef(
                "export_audio",
                label="Include audio",
                tooltip="Process subsets with corresponding audio",
                default=False,
            ),
            BoolDef(
                "sourceResolution",
                label="Source resolution",
                tooltip="Is resoloution taken from timeline or source?",
                default=False,
            ),

            # shotAttr
            UILabelDef(
                label=header_label("Shot Attributes"),
            ),
            NumberDef(
                "workfileFrameStart",
                label="Workfiles Start Frame",
                tooltip="Set workfile starting frame number",
                default=presets.get("workfileFrameStart", 1001),
            ),
            NumberDef(
                "handleStart",
                label="Handle Start (head)",
                tooltip="Handle at start of clip",
                default=presets.get("handleStart", 0),
            ),
            NumberDef(
                "handleEnd",
                label="Handle End (tail)",
                tooltip="Handle at end of clip",
                default=presets.get("handleEnd", 0),
            ),           
        ]

    def create(self, subset_name, instance_data, pre_create_data):
        super(CreateShotClip, self).create(subset_name,
                                           instance_data,
                                           pre_create_data)

        instance_data["clip_variant"] = pre_create_data["clip_variant"]
        instance_data["task"] = None


        if not self.timeline:
            raise CreatorError(
                "You must be in an active timeline to "
                "create the publishable clips.\n\n"
                "Go into a timeline and then reset the publisher."
            )

        if not self.selected:
            if pre_create_data.get("use_selection", False):
                raise CreatorError(
                    "No Chocolate-colored clips found from "
                    "timeline.\n\nTry changing clip(s) color "
                    "or disable clip color restriction."
                )
            else:
                raise CreatorError(
                    "No clips found on current timeline."
                )
        self.log.info(f"Selected: {self.selected}")

        audio_clips = get_current_timeline_items(track_type="audio")
        if not audio_clips and pre_create_data.get("export_audio"):
            raise CreatorError(
                "You must have audio in your active "
                "timeline in order to export audio."
            )            

        # sort selected trackItems by vSync track
        sorted_selected_track_items = []
        unsorted_selected_track_items = []
        v_sync_track = pre_create_data.get("vSyncTrack", "")
        for track_item_data in self.selected:
            if track_item_data["track"]["name"] in v_sync_track:
                sorted_selected_track_items.append(track_item_data)
            else:
                unsorted_selected_track_items.append(track_item_data)

        sorted_selected_track_items.extend(unsorted_selected_track_items)

        # create media bin for compound clips (trackItems)
        media_pool_folder = create_bin(self.timeline.GetName())

        # detect enabled creators for review, plate and audio
        all_creators = {
            "io.ayon.creators.resolve.shot": True,
            "io.ayon.creators.resolve.plate": True,
            "io.ayon.creators.resolve.audio": pre_create_data.get("export_audio", False),
        }
        enabled_creators = tuple(cre for cre, enabled in all_creators.items() if enabled)

        instances = []
        for index, track_item_data in enumerate(sorted_selected_track_items):

            # Compute and store resolution metadata from mediapool clip.
            resolution_data = lib.get_clip_resolution_from_media_pool(track_item_data)
            item_unique_id = track_item_data["clip"]["item"].GetUniqueId()
            instance_data.update({
                "clip_index": item_unique_id,
                "clip_source_resolution": resolution_data,
            })

            # convert track item to timeline media pool item
            publish_clip = plugin.PublishableClip(
                track_item_data,
                pre_create_data,
                media_pool_folder,
                rename_index=index,
                data=instance_data  # insert additional data in instance_data
            )
            track_item = publish_clip.convert()
            if track_item is None:
                # Ignore input clips that do not convert into a track item
                # from `PublishableClip.convert`
                continue

            self.log.info(
                "Processing track item data: {} (index: {})".format(
                    track_item_data, index)
            )

            # Delete any existing instances previously generated for the clip.
            prev_tag_data = lib.get_timeline_item_ayon_tag(track_item)            
            if prev_tag_data:
                for creator_id, inst_data in prev_tag_data[_CONTENT_ID].items():
                    creator = self.create_context.creators[creator_id]
                    prev_instances = [
                        inst for inst_id, inst 
                        in self.create_context.instances_by_id.items()
                        if inst_id == inst_data["instance_id"] 
                    ]
                    creator.remove_instances(prev_instances)

            # Create new product(s) instances.
            clip_instances = {}
            shot_creator_id = "io.ayon.creators.resolve.shot"
            for creator_id in enabled_creators:
                creator = self.create_context.creators[creator_id]
                sub_instance_data = copy.deepcopy(instance_data)
                shot_folder_path = sub_instance_data["folderPath"]

                # Shot creation
                if creator_id == shot_creator_id:
                    track_item_duration = track_item.GetDuration()
                    workfileFrameStart = \
                        sub_instance_data["workfileFrameStart"]
                    sub_instance_data.update({
                        "creator_attributes": {
                            "workfileFrameStart": workfileFrameStart,
                            "handleStart": sub_instance_data["handleStart"],
                            "handleEnd": sub_instance_data["handleEnd"],
                            "frameStart": workfileFrameStart,
                            "frameEnd": (workfileFrameStart + 
                                track_item_duration),
                            "clipIn": track_item.GetStart(),
                            "clipOut": track_item.GetEnd(),
                            "clipDuration": track_item_duration,
                            "sourceIn": track_item.GetLeftOffset(), 
                            "sourceOut": (track_item.GetLeftOffset() + 
                                track_item_duration),
                        },
                        "label": (
                            f"{shot_folder_path} shot"
                        ),
                    })

                # Plate, Audio
                # insert parent instance data to allow
                # metadata recollection as publish time.
                else:
                    parenting_data = clip_instances[shot_creator_id]
                    sub_instance_data.update({
                        "parent_instance_id": parenting_data["instance_id"],
                        "label": (
                            f"{shot_folder_path} "
                            f"{creator.product_type}"
                        ),                        
                        "creator_attributes": {
                            "parentInstance": parenting_data["label"],
                        }
                    })

                    if creator_id == "io.ayon.creators.resolve.plate":
                        sub_instance_data["creator_attributes"].update({
                            "vSyncOn": pre_create_data["vSyncOn"],
                            "vSyncTrack": pre_create_data["vSyncTrack"],                            
                        })

                instance = creator.create(sub_instance_data, None)
                instance.transient_data["track_item"] = track_item            
                self._add_instance_to_context(instance)
                clip_instances[creator_id] = instance.data_to_store()

            # insert clip unique ID and created instances
            # data as track_item metadata, to retrieve those
            # during collections and publishing phases
            lib.imprint(
                track_item,
                data={
                    _CONTENT_ID: clip_instances,
                    "clip_index": item_unique_id,
                },
            )
            track_item.SetClipColor(constants.PUBLISH_CLIP_COLOR)
            instances.extend(list(clip_instances.values()))

        return instances

    def _create_and_add_instance(self, data, creator_id, 
            timeline_item, instances):
        """
        Args:
            data (dict): The data to re-recreate the instance from.
            creator_id (str): The creator id to use.
            timeline_item (obj): The associated timeline item.
            instances (list): Result instance container.

        Returns:
            CreatedInstance: The newly created instance.
        """
        creator = self.create_context.creators[creator_id]
        instance = creator.create(data, None)
        instance.transient_data["track_item"] = timeline_item
        self._add_instance_to_context(instance)
        instances.append(instance)
        return instance

    def _handle_legacy_marker(self, tag_data, timeline_item, instances):
        """ Convert OpenPypeData to AYON data.

        Args:
            tag_data (dict): The legacy marker data.
            timline_item (obj): The associated Resolve item.
            instances (list): Result instance container.
        """
        clip_instances = {}
        item_unique_id = timeline_item.GetUniqueId()
        tag_data.update({
            "task": self.create_context.get_current_task_name(),
            "clip_index": item_unique_id,
        })

        # create parent shot
        creator_id = "io.ayon.creators.resolve.shot"
        shot_data = tag_data.copy()
        inst = self._create_and_add_instance(
            shot_data, creator_id, timeline_item, instances) 
        clip_instances[creator_id] = inst.data_to_store()

        # create children plate
        creator_id = "io.ayon.creators.resolve.plate"
        plate_data = tag_data.copy()
        plate_data.update({
            "parent_instance_id": inst["instance_id"],
            "clip_variant": tag_data["variant"],
            "creator_attributes": {
                "parentInstance": inst["label"],
            }            
        })
        inst = self._create_and_add_instance(
            plate_data, creator_id, timeline_item, instances) 
        clip_instances[creator_id] = inst.data_to_store()

        # Update marker with new version data.
        timeline_item.DeleteMarkersByColor(constants.AYON_MARKER_COLOR)
        lib.imprint(
            timeline_item,
            data={
                _CONTENT_ID: clip_instances,
                "clip_index": item_unique_id,
            },
        )

    def collect_instances(self):
        """Collect all created instances from current timeline."""
        all_timeline_items = lib.get_current_timeline_items()
        instances = []
        for timeline_item_data in all_timeline_items:
            timeline_item = timeline_item_data["clip"]["item"]

            # get (legacy) openpype tag data
            # Backwards compatible (Deprecated since 24/09/05)
            tag_data = lib.get_ayon_marker(
                timeline_item,
                tag_name=constants.LEGACY_OPENPYPE_MARKER_NAME
            )
            if tag_data:
                self._handle_legacy_marker(
                    tag_data, timeline_item, instances)
                continue

            # get AyonData tag data 
            tag_data = lib.get_timeline_item_ayon_tag(timeline_item)
            if not tag_data:
                continue

            for creator_id, data in tag_data.get(_CONTENT_ID, {}).items():
                self._create_and_add_instance(
                        data, creator_id, timeline_item, instances)

        return instances

    def update_instances(self, update_list):
        """Never called, update is handled via _ResolveInstanceCreator."""
        pass

    def remove_instances(self, instances):
        """Never called, removal is handled via _ResolveInstanceCreator."""
        pass

