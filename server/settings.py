from pydantic import validator
from ayon_server.settings import (
    BaseSettingsModel,
    SettingsField,
    ensure_unique_names,
    task_types_enum
)

from .imageio import ResolveImageIOModel


def _intermediate_buildin_format_enum():
    return [
        {"value": "MP4", "label": "MP4"},
        {"value": "QuickTime", "label": "QuickTime"},
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


def _buildin_presets():
    return [
        {
            "label": "AYON QuickTime H264",
            "value": "{ayon_render_presets}/AYON_QuickTime_H264.xml"
        },
        {
            "label": "AYON QuickTime H265",
            "value": "{ayon_render_presets}/AYON_QuickTime_H265.xml"
        },
        {
            "label": "AYON QuickTime Prores422Hq",
            "value": "{ayon_render_presets}/AYON_QuickTime_Prores422Hq.xml"
        },
        {
            "label": "AYON QuickTime ProresLT",
            "value": "{ayon_render_presets}/AYON_QuickTime_ProresLT.xml"
        },
        {
            "label": "AYON QuickTime ProresXQ",
            "value": "{ayon_render_presets}/AYON_QuickTime_ProresXQ.xml"
        },
    ]


def _preset_types_enum():
    return [
        {"value": "custom_preset", "label": "Custom"},
        {"value": "builtin_preset", "label": "Built-in"},
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


class BuildinIntermediateFormatModel(BaseSettingsModel):
    _layout = "expanded"
    format: str = SettingsField(
        "QuickTime",
        title="Format",
        enum_resolver=_intermediate_buildin_format_enum,
    )
    preset_path: str = SettingsField(
        "{ayon_render_presets}/AYON_QuickTime_H264.xml",
        title="Preset",
        enum_resolver=_buildin_presets,
    )
    codec: str = SettingsField(
        "H.264",
        title="Codec",
    )


class CustomIntermediateFormatModel(BaseSettingsModel):
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


class IntermediatePresetModel(BaseSettingsModel):
    """Intermediate Preset

    - Preset Name
    - Filter by task Types
    - Filter by task names
    - Path to Preset
    - Format
    - Codec
    - export_otio
    - otio_rootless

    """
    name: str = SettingsField(
        "",
        title="Name"
    )
    task_types: list[str] = SettingsField(
        default_factory=list,
        title="Task types",
        enum_resolver=task_types_enum
    )
    task_names: list[str] = SettingsField(
        default_factory=list,
        title="Task names"
    )
    preset_type: str = SettingsField(
        "buildin_preset",
        title="Preset type",
        enum_resolver=_preset_types_enum,
        conditional_enum=True,
    )
    buildin_preset: BuildinIntermediateFormatModel = SettingsField(
        default_factory=BuildinIntermediateFormatModel,
        title="Buildin Preset",
    )
    custom_preset: CustomIntermediateFormatModel = SettingsField(
        default_factory=CustomIntermediateFormatModel,
        title="Custom Preset",
    )
    export_otio: bool = SettingsField(
        title="Export OTIO",
        description="When enabled AYON will export OTIO file"
        " along with intermediate file.",
    )
    otio_rootless: bool = SettingsField(
        title="Use rootless OTIO paths",
        description="When enabled AYON will convert all paths"
        " in OTIO to be rootless.",
    )


class EditorialPackageModels(BaseSettingsModel):
    """Editorial Package
    """
    intermediate_presets: list[IntermediatePresetModel] = SettingsField(
        default_factory=list,
        title="Intermediate presets",
        description=(
            "Intermediate presets to be used in Editorial Package creator. The"
            " name must be unique."
        )
    )

    @validator("intermediate_presets")
    def validate_unique_outputs(cls, value):
        ensure_unique_names(value)
        return value


class CreatorPluginsModel(BaseSettingsModel):
    CreateShotClip: CreateShotClipModels = SettingsField(
        default_factory=CreateShotClipModels,
        title="Create Shot Clip"
    )
    EditorialPackage: EditorialPackageModels = SettingsField(
        default_factory=EditorialPackageModels,
        title="Editorial Package"
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
        },
        "EditorialPackage": {
            "intermediate_presets": [
                {
                    "name": "AYON_intermediates",
                    "task_types": [],
                    "task_names": [],
                    "preset_type": "builtin_preset",
                    "export_otio": True,
                    "otio_rootless": True,
                }
            ]
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
    }
}
