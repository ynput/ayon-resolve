import os
import sys
from datetime import datetime, timedelta, timezone
from ayon_core.pipeline import anatomy

resolve_script_api = os.path.expandvars(r"%PROGRAMDATA%\Blackmagic Design\DaVinci Resolve\Support\Developer\Scripting")
sys.path.append(f"{resolve_script_api}/Modules")
sys.path.append(f"{resolve_script_api}/Examples")
AYON_PROJECT_ROOT = str(anatomy.Anatomy().roots['internal'])


def get_application():
    from python_get_resolve import GetResolve
    resolve = app.GetResolve()
    print(f"Resolve: {resolve}")
    return resolve

def get


def main():
    resolve = get_application()
    project_manager = resolve.GetProjectManager()
    project = project_manager.GetCurrentProject()
    media_pool = project.GetMediaPool()

    pst_offset = timedelta(hours=-7)
    pst = timezone(pst_offset)
    now_pst = datetime.now(pst)
    date_str = now_pst.strftime("%Y%m%d")

    # output_path = f"{AYON_PROJECT_ROOT}/editorial/footage"
    output_path = "D:/Test/footage"
    success = False

    source_folder = os.path.join(f"{AYON_PROJECT_ROOT}/editorial/footage", date_str)
    print("Import path:", source_folder)
    print("Output path:", output_path)

    render_preset_path = f"{AYON_PROJECT_ROOT}/scripts/Halon Render.xml"
    is_preset_imported = resolve.ImportRenderPreset(render_preset_path)
    print(f"Preset path: {render_preset_path} {is_preset_imported}")
    if not is_preset_imported:
        preset_name = "Halon Render"
        preset_loaded = project.LoadRenderPreset(preset_name)
        if not preset_loaded:
            raise Exception("Failed to load render preset.")


    mxf_files = [f for f in os.listdir(source_folder) if f.lower().endswith(".mxf")]
    export_folder = os.path.join(source_folder, "output")
    if not os.path.exists(export_folder):
        os.mkdir(export_folder)

    if len(mxf_files) > 0:
        success = True

    for index, filename in enumerate(mxf_files):
        full_path = os.path.join(source_folder, filename)
        timeline_name = f"{filename}"
        print(f"🔄 Importing: {full_path}")

        media_pool_items = media_pool.ImportMedia([full_path])
        if not media_pool_items:
            print(f"❌ Failed to import: {filename}")
            continue

        media_pool_item = media_pool_items[0]
        new_timeline = media_pool.CreateEmptyTimeline(timeline_name)

        if not media_pool.AppendToTimeline([media_pool_item]):
            print(f"❌ Failed to append clip to timeline: {timeline_name}")
            continue

        render_settings = {
        "TargetDir": f"{os.path.join(output_path, date_str, 'output')}",
        "CustomName": timeline_name
        }
        success = project.SetRenderSettings(render_settings)
        project.SetCurrentTimeline(new_timeline)
        project.AddRenderJob()

    if success and project.StartRendering():
        print(f"🚀 Render started...")
        while project.IsRenderingInProgress():
            pass
        print(f"✅ Render finished")
    else:
        print(f"❌ Render failed to start")


if __name__ == "__main__":
    main()