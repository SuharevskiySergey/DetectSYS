"""One-time creation of separate eyelid assets; run in Unreal editor Python.

Refuses existing destination assets; never overwrites the source LAPA5 model.
Does not assign the result to a Blueprint: inspect/verify it before switching.
"""

from pathlib import Path
import sys

import unreal

ROOT = Path(unreal.Paths.project_dir()).resolve()
sys.path.insert(0, str(ROOT / "tools"))
from generate_lapa5_lid import write_obj

FOLDER = "/Game/BeholderPrototype"
MESH_NAME = "SM_Lapa5_EyelidShell"
MATERIAL_NAME = "M_Lapa5_EyelidGeometry"
MESH_PATH = f"{FOLDER}/{MESH_NAME}"
MATERIAL_PATH = f"{FOLDER}/Materials/{MATERIAL_NAME}"


def build():
    for path in (MESH_PATH, MATERIAL_PATH):
        if unreal.EditorAssetLibrary.does_asset_exist(path):
            raise RuntimeError(f"Refusing to overwrite existing asset: {path}")
    filename = write_obj(ROOT / "Saved/Generated/Lapa5Lid.obj")
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
    task = unreal.AssetImportTask()
    task.filename = str(filename)
    task.destination_path = FOLDER
    task.destination_name = MESH_NAME
    task.automated = True
    task.replace_existing = False
    task.save = True
    task.factory = unreal.FbxFactory()
    task.options = options
    assets = unreal.AssetToolsHelpers.get_asset_tools()
    assets.import_asset_tasks([task])
    mesh = unreal.load_asset(MESH_PATH)
    if not isinstance(mesh, unreal.StaticMesh):
        raise RuntimeError(f"Static mesh import failed: {task.imported_object_paths}")

    material = assets.create_asset(MATERIAL_NAME, f"{FOLDER}/Materials",
                                   unreal.Material, unreal.MaterialFactoryNew())
    finish_material(material, mesh)


def finish_material(material, mesh):
    """Fill an EMPTY material graph. Useful for resuming a failed first import."""
    library = unreal.MaterialEditingLibrary
    if library.get_num_material_expressions(material):
        raise RuntimeError("Material graph is not empty; refusing to overwrite it")
    material.set_editor_property("blend_mode", unreal.BlendMode.BLEND_OPAQUE)
    material.set_editor_property("two_sided", False)
    material.set_editor_property("tangent_space_normal", False)

    def node(cls, x, y):
        return library.create_material_expression(material, cls, x, y)

    def connect(source, target, target_pin, output=""):
        if not library.connect_material_expressions(source, output, target, target_pin):
            raise RuntimeError(f"Failed connection to {target_pin}")

    position = node(unreal.MaterialExpressionPreSkinnedPosition, -1100, 0)
    uv = node(unreal.MaterialExpressionTextureCoordinate, -1100, 180)
    opening = node(unreal.MaterialExpressionScalarParameter, -1100, 340)
    opening.set_editor_property("parameter_name", "Opening")
    opening.set_editor_property("default_value", 0)
    aperture = node(unreal.MaterialExpressionScalarParameter, -1100, 500)
    aperture.set_editor_property("parameter_name", "MaxApertureRadians")
    aperture.set_editor_property("default_value", 1)
    def custom_node(y):
        result = node(unreal.MaterialExpressionCustom, -700, y)
        result.set_editor_property("description", "Geometric aperture, inner shell and thickness rim")
        result.set_editor_property("output_type", unreal.CustomMaterialOutputType.CMOT_FLOAT3)
        inputs = []
        for name in ("LocalPosition", "UV", "Opening", "MaxAperture"):
            entry = unreal.CustomInput()
            entry.set_editor_property("input_name", name)
            inputs.append(entry)
        result.set_editor_property("inputs", inputs)
        normal_output = unreal.CustomOutput()
        normal_output.set_editor_property("output_name", "NormalLocal")
        normal_output.set_editor_property("output_type", unreal.CustomMaterialOutputType.CMOT_FLOAT3)
        result.set_editor_property("additional_outputs", [normal_output])
        result.set_editor_property("code", (ROOT / "tools/shaders/lapa5_lid.hlsl").read_text(encoding="utf-8"))
        return result

    custom = custom_node(0)
    normal_custom = custom_node(850)
    # UE 5.6 PreSkinnedPosition is vertex-only. The pixel-stage normal needs an
    # interpolated copy, NOT a shared custom expression feeding both stages.
    interpolator = node(unreal.MaterialExpressionVertexInterpolator, -1100, 850)
    connect(position, interpolator, library.get_material_expression_input_names(interpolator)[0])
    for expression, pos in ((custom, position), (normal_custom, interpolator)):
        for source, name in ((pos, "LocalPosition"), (uv, "UV"),
                             (opening, "Opening"), (aperture, "MaxAperture")):
            connect(source, expression, name)
    for expression, output_name, prop, y in (
            (custom, "", unreal.MaterialProperty.MP_WORLD_POSITION_OFFSET, 0),
            (normal_custom, "NormalLocal", unreal.MaterialProperty.MP_NORMAL, 250)):
        transform = node(unreal.MaterialExpressionTransform, -250, y)
        transform.set_editor_property("transform_source_type", unreal.MaterialVectorCoordTransformSource.TRANSFORMSOURCE_LOCAL)
        transform.set_editor_property("transform_type", unreal.MaterialVectorCoordTransform.TRANSFORM_WORLD)
        transform_inputs = library.get_material_expression_input_names(transform)
        if len(transform_inputs) != 1:
            raise RuntimeError(f"Unexpected transform inputs: {transform_inputs}")
        connect(expression, transform, transform_inputs[0], output_name)
        if not library.connect_material_property(transform, "", prop):
            raise RuntimeError(f"Failed material output: {prop}")
    tint = node(unreal.MaterialExpressionVectorParameter, -250, 500)
    tint.set_editor_property("parameter_name", "Tint")
    tint.set_editor_property("default_value", unreal.LinearColor(0.18, 0.035, 0.055, 1))
    roughness = node(unreal.MaterialExpressionScalarParameter, -250, 700)
    roughness.set_editor_property("parameter_name", "Roughness")
    roughness.set_editor_property("default_value", 0.65)
    library.connect_material_property(tint, "", unreal.MaterialProperty.MP_BASE_COLOR)
    library.connect_material_property(roughness, "", unreal.MaterialProperty.MP_ROUGHNESS)
    library.recompile_material(material)
    mesh.set_material(0, material)
    mesh.set_editor_property("positive_bounds_extension", unreal.Vector(1, 1, 1))
    mesh.set_editor_property("negative_bounds_extension", unreal.Vector(1, 1, 1))
    unreal.EditorAssetLibrary.save_loaded_asset(material)
    unreal.EditorAssetLibrary.save_loaded_asset(mesh)
    print(f"Created {MESH_PATH} and {MATERIAL_PATH}; not assigned to the head yet.")


if __name__ == "__main__":
    build()
