"""Read-only calibrated claw geometry helpers for Unreal editor Python."""

import json
from pathlib import Path

import unreal


def claw_vertices_world(head):
    mesh = next(c for c in head.get_components_by_class(unreal.SkeletalMeshComponent)
                if c.get_name() == "HeadMesh")
    fixture = json.loads((Path(__file__).parent / "fixtures/lapa5_claw_vertices.json").read_text(encoding="utf-8"))
    for bone, vertices in fixture["bones"].items():
        assert mesh.get_bone_index(bone) >= 0, f"Missing claw bone: {bone}"
        bone_world = mesh.get_socket_transform(bone, unreal.RelativeTransformSpace.RTS_WORLD)
        yield [bone_world.transform_location(unreal.Vector(*vertex)) for vertex in vertices]
