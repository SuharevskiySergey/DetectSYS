"""Read-only regression checks; run with Unreal editor Python, not system Python.

Checks the saved rig's actual pins/links. No FBX export or running PIE is needed.
"""

import json
import math
import re

import unreal


def vector(text):
    values = {key: float(value) for key, value in re.findall(
        r"([XYZ])=([-+\d.eE]+)", text)}
    return unreal.Vector(values["X"], values["Y"], values["Z"])


def length(v):
    return math.sqrt(v.x * v.x + v.y * v.y + v.z * v.z)


def validate():
    rig = unreal.load_asset("/Game/BeholderPrototype/CR_Lapa5_Head")
    if rig is None:
        raise AssertionError("CR_Lapa5_Head is missing")
    graph = rig.get_model()
    center = rig.hierarchy.get_global_transform(
        unreal.RigElementKey(name="Sphere", type=unreal.RigElementType.BONE),
        initial=True).translation
    rows = []
    for i, bone in enumerate(("Circle_004", "Circle_003", "Circle_005")):
        def pin(path):
            result = graph.find_pin(path)
            if result is None:
                raise AssertionError(f"Missing pin: {path}")
            return result

        def default(path):
            return pin(path).get_default_value()

        initial = rig.hierarchy.get_global_transform(
            unreal.RigElementKey(name=bone, type=unreal.RigElementType.BONE),
            initial=True)
        expected = initial.inverse_transform_location(center)
        pivot_a = vector(default(f"PivotOffset{i}.A"))
        pivot_b = vector(default(f"RotatedPivot{i}.Vector"))
        assert length(pivot_a - expected) < 1e-6, f"{bone}: pivot is not sphere center"
        assert length(pivot_b - expected) < 1e-6, f"{bone}: rotation uses another pivot"
        assert float(default(f"RotateClaw{i}.Weight")) == 1, f"{bone}: blended offset"
        assert not pin(f"RotateClaw{i}.Weight").get_linked_source_pins(), bone
        assert math.isclose(float(default(f"Angle{i}.B")), math.pi / 2, abs_tol=1e-6), bone
        assert length(vector(default(f"RotateClaw{i}.OffsetTransform.Scale3D"))
                      - unreal.Vector(1, 1, 1)) < 1e-6, f"{bone}: shape is scaled"
        assert default(f"GetClaw{i}.Control") == f"Claw{i}", bone
        assert f'Name="{bone}"' in default(f"RotateClaw{i}.Item"), bone
        links = {
            f"Angle{i}.A": f"GetClaw{i}.FloatValue",
            f"Rotation{i}.Angle": f"Angle{i}.Result",
            f"RotatedPivot{i}.Transform": f"Rotation{i}.Result",
            f"PivotOffset{i}.B": f"RotatedPivot{i}.Result",
            f"RotateClaw{i}.OffsetTransform.Rotation": f"Rotation{i}.Result",
            f"RotateClaw{i}.OffsetTransform.Translation": f"PivotOffset{i}.Result",
        }
        for target, source in links.items():
            actual = [p.get_pin_path() for p in pin(target).get_linked_source_pins()]
            assert actual == [source], f"{target}: expected {source}, got {actual}"
        local_axis = vector(default(f"Rotation{i}.Axis"))
        assert abs(length(local_axis) - 1) < 1e-6, f"{bone}: axis is not normalized"
        axis = initial.rotation.rotate_vector(local_axis)
        assert abs(axis.z) < 1e-5, f"{bone}: motion leaves its radial plane"
        rows.append({"bone": bone, "pivotErrorLocal": length(pivot_a - expected),
                     "orbitDegrees": 90, "passed": True})
    return {"motion": "sphere_center", "checks": rows, "passed": True}


if __name__ == "__main__":
    print(json.dumps(validate(), indent=2))
