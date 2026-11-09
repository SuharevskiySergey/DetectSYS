import unittest
from unittest.mock import patch

from inspect_fbx_skin import inspect


class InspectSkinTests(unittest.TestCase):
    @patch("pathlib.Path.read_text", return_value='''
        Geometry: 1, "Geometry::Mesh", "Mesh" {
            Vertices: *6 { a: 1,2,3,4,5,6 }
        }
        Model: 2, "Model::Claw", "LimbNode" {}
        Deformer: 3, "SubDeformer::", "Cluster" {
            Indexes: *2 { a: 0,1 }
            Weights: *2 { a: 1,0.0001 }
            Transform: *1 { a: 0 }
        }
        C: "OO",2,3
    ''')
    def test_cluster_connections_and_weight_threshold(self, _read):
        rows = inspect("unused.fbx")
        self.assertEqual(rows[0]["bone"], "Claw")
        self.assertEqual(rows[0]["vertices"], [[1.0, 2.0, 3.0]])
        self.assertEqual(rows[0]["count"], 1)

    @patch("pathlib.Path.read_text", return_value='''
        Model: 2, "Model::Empty", "LimbNode" {}
        Deformer: 3, "SubDeformer::", "Cluster" {
            Transform: *1 { a: 0 }
        }
        C: "OO",2,3
    ''')
    def test_unweighted_bone(self, _read):
        rows = inspect("unused.fbx")
        self.assertEqual(rows[0]["bone"], "Empty")
        self.assertEqual(rows[0]["vertices"], [])


if __name__ == "__main__":
    unittest.main()
