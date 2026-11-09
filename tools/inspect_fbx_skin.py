"""Read-only summary of vertex groups in an Unreal ASCII FBX export."""

import json
import re
import sys
from pathlib import Path


def array(text, name, cast=float):
    match = re.search(rf"\b{name}:\s*\*\d+\s*\{{\s*a:\s*([^}}]+)\}}", text)
    return [cast(value.strip()) for value in match[1].split(",")] if match else []


def inspect(path):
    text = Path(path).read_text(encoding="utf-8-sig")
    values = array(text, "Vertices")
    vertices = [values[i:i + 3] for i in range(0, len(values), 3)]
    models = dict(re.findall(r'Model:\s*(\d+),\s*"Model::([^\"]+)"', text))
    connections = re.findall(r'C:\s*"OO",\s*(\d+),\s*(\d+)', text)
    result = []
    for match in re.finditer(r'Deformer:\s*(\d+),[^\n]+"Cluster"\s*\{', text):
        start = match.end()
        depth = 1
        end = start
        while depth:
            depth += (text[end] == "{") - (text[end] == "}")
            end += 1
        block = text[start:end]
        indices = array(block, "Indexes", int)
        weights = array(block, "Weights")
        bone = next((models[src] for src, dst in connections
                     if dst == match[1] and src in models), "unknown")
        points = [vertices[i] for i, w in zip(indices, weights) if w > 0.001]
        result.append({"bone": bone, "vertices": points,
                       "weights": weights, "count": len(points)})
    return result


if __name__ == "__main__":
    print(json.dumps(inspect(sys.argv[1]), ensure_ascii=False, indent=2))
