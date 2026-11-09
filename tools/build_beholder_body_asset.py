"""Import the separate eight-socket body; never overwrite an existing asset."""
from pathlib import Path
import sys

import unreal

ROOT = Path(unreal.Paths.project_dir()).resolve()
sys.path.insert(0, str(ROOT / 'tools'))
from generate_beholder_body import write_obj

PATH = '/Game/BeholderPrototype/Body/SM_BeholderEightSocketBody'


def build():
    assert not unreal.EditorAssetLibrary.does_asset_exist(PATH), f'Refusing to overwrite {PATH}'
    material = unreal.load_asset('/Game/BeholderPrototype/Materials/M_Claw_Prototype')
    assert material
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
    task.filename = str(write_obj(ROOT / 'Saved/Generated/BeholderEightSocketBody.obj'))
    task.destination_path, task.destination_name = PATH.rsplit('/', 1)
    task.automated = True
    task.replace_existing = False
    task.save = False
    task.factory = unreal.FbxFactory()
    task.options = options
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    mesh = unreal.load_asset(PATH)
    assert isinstance(mesh, unreal.StaticMesh)
    mesh.set_material(0, material)
    unreal.EditorAssetLibrary.save_loaded_asset(mesh)
    print('Created', PATH)


if __name__ == '__main__':
    build()
