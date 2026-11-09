"""Import rigid sleeves in Unreal; default refuses existing destinations."""

from pathlib import Path
import sys

import unreal

ROOT = Path(unreal.Paths.project_dir()).resolve()
sys.path.insert(0, str(ROOT / "tools"))
from generate_beholder_telescope import COUNT, write_obj

FOLDER = "/Game/BeholderPrototype/Telescopic"


def build(reimport_generated=False):
    paths = [f"{FOLDER}/SM_TelescopeSleeve{i:02d}" for i in range(COUNT)]
    for i, path in enumerate(paths):
        if unreal.EditorAssetLibrary.does_asset_exist(path):
            if not reimport_generated:
                raise RuntimeError(f"Refusing to overwrite {path}")
            mesh = unreal.load_asset(path)
            source = mesh.get_editor_property("asset_import_data").get_first_filename()
            expected = ROOT / f"Saved/Generated/TelescopeSleeve{i:02d}.obj"
            assert Path(source).resolve() == expected.resolve(), f"Not our generated source: {path}"
    material = unreal.load_asset("/Game/BeholderPrototype/Materials/M_Claw_Prototype")
    assert material is not None, "Prototype material missing"
    tasks = []
    for i, path in enumerate(paths):
        options = unreal.FbxImportUI()
        options.automated_import_should_detect_type = False
        options.import_mesh = True
        options.import_as_skeletal = False
        options.mesh_type_to_import = unreal.FBXImportType.FBXIT_STATIC_MESH
        options.import_materials = False
        options.import_textures = False
        data = options.static_mesh_import_data
        data.auto_generate_collision = False
        data.convert_scene = False
        data.convert_scene_unit = False
        data.generate_lightmap_u_vs = False
        data.normal_import_method = unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS
        task = unreal.AssetImportTask()
        task.filename = str(write_obj(ROOT / f"Saved/Generated/TelescopeSleeve{i:02d}.obj", i))
        task.destination_path = FOLDER
        task.destination_name = path.rsplit("/", 1)[-1]
        task.automated = True
        task.replace_existing = reimport_generated
        task.save = False
        task.factory = unreal.FbxFactory()
        task.options = options
        tasks.append(task)
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks(tasks)
    for path in paths:
        mesh = unreal.load_asset(path)
        assert isinstance(mesh, unreal.StaticMesh), f"Import failed: {path}"
        mesh.set_material(0, material)
        unreal.EditorAssetLibrary.save_loaded_asset(mesh)
    verb = "Reimported generated" if reimport_generated else "Created new"
    print(f"{verb} {COUNT} rigid hollow sleeves in {FOLDER}")


if __name__ == "__main__":
    build()
