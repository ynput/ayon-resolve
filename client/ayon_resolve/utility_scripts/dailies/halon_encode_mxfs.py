import os
import sys
from datetime import datetime, timedelta, timezone

# Bunch of crap we have to path
resolve_script_api = os.path.expandvars(r"%PROGRAMDATA%\Blackmagic Design\DaVinci Resolve\Support\Developer\Scripting")
sys.path.append(f"{resolve_script_api}/Modules")
sys.path.append(f"{resolve_script_api}/Examples")
resolve_script_lib = r"C:\Program Files\Blackmagic Design\DaVinci Resolve\fusionscript.dll"

# Path to saved xml of render preset
render_preset_path = "C:/ProgramData/Blackmagic Design/DaVinci Resolve/Fusion/Scripts/Utility/Halon Render.xml"

# Get current PYTHONPATH or default to empty string
current_pythonpath = os.environ.get("PYTHONPATH", "")
new_pythonpath = f"{current_pythonpath};{resolve_script_api}\\Modules" if current_pythonpath else f"{resolve_script_api}\\Modules"

# Set environment variables
os.environ["RESOLVE_SCRIPT_API"] = resolve_script_api
os.environ["RESOLVE_SCRIPT_LIB"] = resolve_script_lib
os.environ["PYTHONPATH"] = new_pythonpath

# This is having to be manually referenced to access Resolve (see crap above)
import DaVinciResolveScript as dvr_script



def get_application():
    from python_get_resolve import GetResolve
    resolve = app.GetResolve()
    print(f"Resolve: {resolve}")
    return resolve


def main():
    resolve = get_application()
    project_manager = resolve.GetProjectManager()
    project = project_manager.GetCurrentProject()
    media_pool = project.GetMediaPool()

    pst_offset = timedelta(hours=-7)
    pst = timezone(pst_offset)
    now_pst = datetime.now(pst)
    date_str = now_pst.strftime("%Y%m%d")

    output_path = "Z:/InProd/inknpaint/editorial/footage"
    # output_path = "D:/Test/footage"

    source_folder = os.path.join("Z:/InProd/inknpaint/editorial/footage", date_str)
    print("Import path:", source_folder)
    print("Output path:", output_path)

    is_preset_imported = resolve.ImportRenderPreset(render_preset_path)
    if not is_preset_imported:
        preset_name = "Halon Render"
        preset_loaded = project.LoadRenderPreset(preset_name)
        if not preset_loaded:
            raise Exception("Failed to load render preset.")


    mxf_files = [f for f in os.listdir(source_folder) if f.lower().endswith(".mxf")]
    export_folder = os.path.join(source_folder, "output")
    if not os.path.exists(export_folder):
        os.mkdir(export_folder)



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