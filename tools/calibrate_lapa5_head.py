"""Run in Unreal's editor Python after exporting Saved/Lapa5_Head_Analysis.fbx.

Read-only calibration of spherical claw motion; writes diagnostics under Saved/.
"""

import json
import math
import sys
from pathlib import Path

import unreal

ROOT = Path(unreal.Paths.project_dir()).resolve()
sys.path.insert(0, str(ROOT / "tools"))
from inspect_fbx_skin import inspect

rig = unreal.load_asset("/Game/BeholderPrototype/CR_Lapa5_Head")
groups = {row["bone"]: row for row in inspect(ROOT / "Saved/Lapa5_Head_Analysis.fbx")}
center = rig.hierarchy.get_global_transform(
    unreal.RigElementKey(name="Sphere", type=unreal.RigElementType.BONE), initial=True).translation
xyz = lambda v: {"x": v.x, "y": v.y, "z": v.z}
length = lambda v: math.sqrt(v.x ** 2 + v.y ** 2 + v.z ** 2)
result = []
for bone in ("Circle_004", "Circle_003", "Circle_005"):
    # The old base edge still defines the motion plane, NOT the rotation pivot.
    # Unreal's FBX export reflects Y.
    points = {tuple(p) for p in groups[bone]["vertices"]}
    base_z = min(p[2] for p in points)
    edge = [unreal.Vector(p[0], -p[1], p[2]) for p in points
            if abs(p[2] - base_z) < 0.01 and math.hypot(p[0], p[1]) > 40]
    if len(edge) != 2:
        raise ValueError(f"{bone}: expected two hinge-edge vertices, got {len(edge)}")
    edge_midpoint = (edge[0] + edge[1]) * 0.5
    axis = edge[1] - edge[0]
    axis.z = 0  # Remove numerical export noise from these radial planes.
    axis = axis / math.sqrt(axis.x ** 2 + axis.y ** 2 + axis.z ** 2)
    radial = edge_midpoint - center
    if axis.y * radial.x - axis.x * radial.y < 0:
        axis = axis * -1
    transform = rig.hierarchy.get_global_transform(
        unreal.RigElementKey(name=bone, type=unreal.RigElementType.BONE), initial=True)
    local_pivot = transform.inverse_transform_location(center)
    local_axis = transform.rotation.unrotate_vector(axis)
    vertices = [unreal.Vector(p[0], -p[1], p[2]) for p in points]
    contact = min(vertices, key=lambda p: length(p - center))
    tip = max(vertices, key=lambda p: length(p - center))
    result.append({"bone": bone, "motion": "sphere_center", "pivotRig": xyz(center),
                   "axisRig": xyz(axis), "pivotLocal": xyz(local_pivot),
                   "axisLocal": xyz(local_axis), "contactRig": xyz(contact),
                   "contactLocal": xyz(transform.inverse_transform_location(contact)),
                   "tipLocal": xyz(transform.inverse_transform_location(tip)),
                   "verticesLocal": [xyz(transform.inverse_transform_location(p)) for p in vertices],
                   "contactRadius": length(contact - center)})
output = json.dumps(result, indent=2)
(ROOT / "Saved/Lapa5_Head_Calibration.json").write_text(output, encoding="utf-8")
print(output)
