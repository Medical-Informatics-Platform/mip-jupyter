import ast
import pathlib
import unittest


class TestNoTableMethods(unittest.TestCase):
    def test_no_table_method_exists_in_package(self):
        root = pathlib.Path(__file__).resolve().parents[1] / "mip"
        offenders = []
        for path in root.rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "table":
                    offenders.append(str(path.relative_to(root)))
        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()
