from pydantic import validator
from ayon_server.settings import (
    BaseSettingsModel,
    SettingsField,
    ensure_unique_names,
    task_types_enum
)

from .imageio import ResolveImageIOModel


def _intermediate_builtin_format_enum():
    return [
        {"value": "QuickTime", "label": "QuickTime"},
        {"value": "EXR", "label": "EXR"},
    ]

def _intermediate_custom_format_enum():
    return [
        {"value": "AVI", "label": "AVI"},
        {"value": "Cineon", "label": "Cineon"},
        {"value": "DCP", "label": "DCP"},
        {"value": "DPX", "label": "DPX"},
        {"value": "EXR", "label": "EXR"},
        {"value": "GIF", "label": "GIF"},
        {"value": "IMF", "label": "IMF"},
        {"value": "JPEG", "label": "JPEG"},
        {"value": "JPEG 2000", "label": "JPEG 2000"},
        {"value": "MJ2", "label": "MJ2"},
        {"value": "MKV", "label": "MKV"},
        {"value": "MP4", "label": "MP4"},
        {"value": "MXF OP-Atom", "label": "MXF OP-Atom"},
        {"value": "MXF OP1A", "label": "MXF OP1A"},
        {"value": "PNG", "label": "PNG"},
        {"value": "QuickTime", "label": "QuickTime"},
        {"value": "TIFF", "label": "TIFF"},
        {"value": "WebP", "label": "WebP"}
    ]


def _builtin_timeline_presets():
    return [
        {
            "label": "QuickTime H264",
            "value": "{ayon_render_presets}/timeline/QuickTime_H264.xml"
        },
        {
            "label": "QuickTime H265",
            "value": "{ayon_render_presets}/timeline/QuickTime_H265.xml"
        },
        {
            "label": "QuickTime Prores422Hq",
            "value": "{ayon_render_presets}/timeline/QuickTime_Prores422Hq.xml"
        },
        {
            "label": "QuickTime ProresLT",
            "value": "{ayon_render_presets}/timeline/QuickTime_ProresLT.xml"
        },
        {
            "label": "QuickTime ProresXQ",
            "value": "{ayon_render_presets}/timeline/QuickTime_ProresXQ.xml"
        },
    ]


def _builtin_plate_presets():
    return [
        {
            "label": "EXR RGB half (DWAA)",
            "value": "{ayon_render_presets}/clip/EXR_RGB_half_(DWAA).xml"
        },
        {
            "label": "EXR RGB float (ZIP)",
            "value": "{ayon_render_presets}/clip/EXR_RGB_float_(ZIP).xml"
        },
    ]


def _preset_types_enum():
    return [
        {"value": "custom_preset", "label": "Custom"},
        {"value": "builtin_preset", "label": "Built-in"},
    ]


def _product_base_types_enum():
    return [
        {"value": "editorial_pkg", "label": "Editorial Package"},
        {"value": "plate", "label": "Plate Clip"},
    ]


def representation_tags_enum():
    return [
        {"value": "review", "label": "Extract review processing"},
        {"value": "delete", "label": "Delete - as intermediate"},
        {"value": "passing", "label": "Skip Extract Review"},
    ]


class CreateShotClipModels(BaseSettingsModel):
    hierarchy: str = SettingsField(
        "{folder}/{sequence}",
        title="Shot parent hierarchy",
        section="Shot Hierarchy And Rename Settings"
    )
    clipRename: bool = SettingsField(
        True,
        title="Rename clips"
    )
    clipName: str = SettingsField(
        "{track}{sequence}{shot}",
        title="Clip name template"
    )
    countFrom: int = SettingsField(
        10,
        title="Count sequence from"
    )
    countSteps: int = SettingsField(
        10,
        title="Stepping number"
    )

    folder: str = SettingsField(
        "shots",
        title="{folder}",
        section="Shot Template Keywords"
    )
    episode: str = SettingsField(
        "ep01",
        title="{episode}"
    )
    sequence: str = SettingsField(
        "sq01",
        title="{sequence}"
    )
    track: str = SettingsField(
        "{_track_}",
        title="{track}"
    )
    shot: str = SettingsField(
        "sh###",
        title="{shot}"
    )

    vSyncOn: bool = SettingsField(
        False,
        title="Enable Vertical Sync",
        section="Vertical Synchronization Of Attributes"
    )

    workfileFrameStart: int = SettingsField(
        1001,
        title="Workfile Start Frame",
        section="Shot Attributes"
    )
    handleStart: int = SettingsField(
        10,
        title="Handle start (head)"
    )
    handleEnd: int = SettingsField(
        10,
        title="Handle end (tail)"
    )
    plate_product_types: list[str] = SettingsField(
        default_factory=list,
        title="Plate Product types",
        description="Optional list of product types for plate products."
    )
    audio_product_types: list[str] = SettingsField(
        default_factory=list,
        title="Audio Product types",
        description="Optional list of product types for audio products."
    )


class BuiltinTimelineFormatModel(BaseSettingsModel):
    _layout = "expanded"
    format: str = SettingsField(
        "QuickTime",
        title="Format",
        enum_resolver=_intermediate_builtin_format_enum,
    )
    preset_path: str = SettingsField(
        "{ayon_render_presets}/timeline/QuickTime_H264.xml",
        title="Preset",
        enum_resolver=_builtin_timeline_presets,
    )
    codec: str = SettingsField(
        "H.264",
        title="Codec",
    )

class BuiltinPlateFormatModel(BaseSettingsModel):
    _layout = "expanded"
    format: str = SettingsField(
        "EXR",
        title="Format",
        enum_resolver=_intermediate_builtin_format_enum,
    )
    preset_path: str = SettingsField(
        "{ayon_render_presets}/clip/EXR_RGB_half_(DWAA).xml",
        title="Preset",
        enum_resolver=_builtin_plate_presets,
    )
    codec: str = SettingsField(
        "RGB half (DWAA)",
        title="Codec",
    )

class CustomPresetModel(BaseSettingsModel):
    _layout = "expanded"
    format: str = SettingsField(
        "QuickTime",
        title="Format",
        enum_resolver=_intermediate_custom_format_enum,
    )
    preset_path: str = SettingsField(
        "",
        title="Preset path",
        placeholder="shared storage path with `{root[work]}` token",
    )
    codec: str = SettingsField(
        "H.264",
        title="Codec",
    )

class TimelineIntermediateFormatModel(BaseSettingsModel):
    _layout = "expanded"
    export_otio: bool = SettingsField(
        True,
        title="Export OTIO",
        description="When enabled AYON will export OTIO file"
        " along with intermediate file.",
        section="Timeline options",
    )
    otio_rootless: bool = SettingsField(
        True,
        title="Use rootless OTIO paths",
        description="When enabled AYON will convert all paths"
        " in OTIO to be rootless.",
    )
    preset_type: str = SettingsField(
        "builtin_preset",
        title="Preset type",
        enum_resolver=_preset_types_enum,
        conditional_enum=True,
        section="Preset options",
    )
    builtin_preset: BuiltinTimelineFormatModel = SettingsField(
        default_factory=BuiltinTimelineFormatModel,
        title="Builtin Preset",
    )
    custom_preset: CustomPresetModel = SettingsField(
        default_factory=CustomPresetModel,
        title="Custom Preset",
    )

class PlateFormatModel(BaseSettingsModel):
    _layout = "expanded"
    preset_type: str = SettingsField(
        "builtin_preset",
        title="Preset type",
        enum_resolver=_preset_types_enum,
        conditional_enum=True,
        section="Preset options",
    )
    builtin_preset: BuiltinPlateFormatModel = SettingsField(
        default_factory=BuiltinPlateFormatModel,
        title="Builtin Preset",
    )
    custom_preset: CustomPresetModel = SettingsField(
        default_factory=CustomPresetModel,
        title="Custom Preset",
    )

class ProductResourcesPresetModel(BaseSettingsModel):
    """Product Resources Preset."""
    name: str = SettingsField(
        "",
        title="Name"
    )
    task_types: list[str] = SettingsField(
        default_factory=list,
        title="Task types",
        enum_resolver=task_types_enum,
        section="Profile filtering",
    )
    task_names: list[str] = SettingsField(
        default_factory=list,
        title="Task names"
    )
    product_base_type: str = SettingsField(
        "editorial_pkg",
        title="Product base type",
        enum_resolver=_product_base_types_enum,
        conditional_enum=True
    )
    editorial_pkg: TimelineIntermediateFormatModel = SettingsField(
        default_factory=TimelineIntermediateFormatModel,
        title="Timeline Attributes",
    )
    plate: PlateFormatModel = SettingsField(
        default_factory=PlateFormatModel,
        title="Plate Attributes",
    )
    tags: list[str] = SettingsField(
        default_factory=list,
        title="Tags",
        enum_resolver=representation_tags_enum,
        description="Currently only partly supporting reviewable workflow.",
        section="Representation attributes",
    )
    custom_tags: list[str] = SettingsField(
        default_factory=list,
        title="Custom Tags",
        description=(
            "Ideal for additional filtering under Extract Review plugin.")
    )
    colorspace: str = SettingsField(
        "",
        title="Colorspace",
        description="The colorspace to be added to colorspace metadata."
    )


class ExtractProductResourcesModel(BaseSettingsModel):
    """Extract Product Resources
    """
    profiles: list[ProductResourcesPresetModel] = SettingsField(
        default_factory=list,
        title="Profiles",
        description=(
            "Additional product resources profiles to be used in product "
            "resource extraction."
        )
    )

    @validator("profiles")
    def validate_unique_outputs(cls, value):
        ensure_unique_names(value)
        return value


class CreatorPluginsModel(BaseSettingsModel):
    CreateShotClip: CreateShotClipModels = SettingsField(
        default_factory=CreateShotClipModels,
        title="Create Shot Clip"
    )


class MetadataMappingModel(BaseSettingsModel):
    """Metadata mapping

    Representation document context data are used for formatting of
    anatomy tokens. Following are supported:
    - version
    - task
    - asset

    """
    name: str = SettingsField(
        "",
        title="Metadata property name"
    )
    value: str = SettingsField(
        "",
        title="Metadata value template"
    )


class LoadMediaModel(BaseSettingsModel):
    clip_color_last: str = SettingsField(
        "Olive",
        title="Clip color for last version"
    )
    clip_color_old: str = SettingsField(
        "Orange",
        title="Clip color for old version"
    )
    media_pool_bin_path: str = SettingsField(
        "Loader/{folder[path]}",
        title="Media Pool bin path template"
    )
    metadata: list[MetadataMappingModel] = SettingsField(
        default_factory=list,
        title="Metadata mapping",
        description=(
            "Set these media pool item metadata values on load and update. The"
            " keys must match the exact Resolve metadata names like"
            " 'Clip Name' or 'Shot'"
        )
    )

    @validator("metadata")
    def validate_unique_outputs(cls, value):
        ensure_unique_names(value)
        return value


class LoaderPluginsModel(BaseSettingsModel):
    LoadMedia: LoadMediaModel = SettingsField(
        default_factory=LoadMediaModel,
        title="Load Media"
    )

class PublishPluginModel(BaseSettingsModel):
    ExtractProductResources: ExtractProductResourcesModel = SettingsField(
        default_factory=ExtractProductResourcesModel,
        title="Extract Product Resources"
    )


class ResolveSettings(BaseSettingsModel):
    launch_ayon_menu_on_start: bool = SettingsField(
        False, title="Launch AYON menu on start of Resolve"
    )
    report_fps_resolution: bool = SettingsField(
        False, title="Set FPS and Resolution from current task"
    )
    imageio: ResolveImageIOModel = SettingsField(
        default_factory=ResolveImageIOModel,
        title="Color Management (ImageIO)"
    )
    create: CreatorPluginsModel = SettingsField(
        default_factory=CreatorPluginsModel,
        title="Creator plugins",
    )
    load: LoaderPluginsModel = SettingsField(
        default_factory=LoaderPluginsModel,
        title="Loader plugins",
    )
    publish: PublishPluginModel = SettingsField(
        default_factory=PublishPluginModel,
        title="Publish plugins",
    )


DEFAULT_VALUES = {
    "launch_ayon_menu_on_start": False,
    "report_fps_resolution": False,
    "create": {
        "CreateShotClip": {
            "hierarchy": "{folder}/{sequence}",
            "clipRename": True,
            "clipName": "{track}{sequence}{shot}",
            "countFrom": 10,
            "countSteps": 10,
            "folder": "shots",
            "episode": "ep01",
            "sequence": "sq01",
            "track": "{_track_}",
            "shot": "sh###",
            "vSyncOn": False,
            "workfileFrameStart": 1001,
            "handleStart": 10,
            "handleEnd": 10
        }
    },
    "load": {
        "LoadMedia": {
            "clip_color_last": "Olive",
            "clip_color_old": "Orange",
            "media_pool_bin_path": (
                "Loader/{folder[path]}"
            ),
            "metadata": [
                {
                    "name": "Comments",
                    "value": "{version[attrib][comment]}"
                },
                {
                    "name": "Shot",
                    "value": "{folder[path]}"
                },
                {
                    "name": "Take",
                    "value": "{product[name]} {version[name]}"
                },
                {
                    "name": "Clip Name",
                    "value": (
                        "{folder[path]} {product[name]} "
                        "{version[name]} ({representation[name]})"
                    )
                }
            ]
        }
    },
    "publish": {
        "ExtractProductResources": {
            "profiles": [
                {
                    "name": "timeline_reviewable",
                    "task_types": [],
                    "task_names": [],
                    "product_base_type": "editorial_pkg",
                    "editorial_pkg": {
                        "preset_type": "builtin_preset",
                    },
                    "tags": ["review", "delete"],
                    "custom_tags": []
                },
                {
                    "name": "plate_exr_dwaa",
                    "task_types": [],
                    "task_names": [],
                    "product_base_type": "plate",
                    "plate": {
                        "preset_type": "builtin_preset"
                    },
                    "tags": ["passing"],
                    "custom_tags": []
                }
            ]
        }
    }
}
