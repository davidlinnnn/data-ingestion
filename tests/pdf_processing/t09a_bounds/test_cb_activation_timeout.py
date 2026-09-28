"""Replay ambiguous activation against CB's real loop without Kubernetes."""
import ast
from pathlib import Path
import unittest


class ActivationTimeoutTest(unittest.TestCase):
    def test_applied_patch_timeout_keeps_identity_for_restoration(self):
        path = Path(__file__).parent / 'normal-topology-cb/controller.py'
        loop = next(node for node in ast.walk(ast.parse(path.read_text()))
                    if isinstance(node, ast.For) and isinstance(node.target, ast.Name)
                    and node.target.id == 'item' and isinstance(node.iter, ast.Name)
                    and node.iter.id == 'rows')
        item = {'metadata': {'namespace':'test', 'name':'owned', 'uid':'exact'}}
        tracked, live = [], []
        def applied_then_timeout(*args):
            live.append(args[0])
            raise TimeoutError('applied, response lost')
        with self.assertRaises(TimeoutError):
            exec(compile(ast.Module(body=[loop], type_ignores=[]), str(path), 'exec'),
                 {'rows':[item], 'activated':tracked, 'patch':applied_then_timeout})
        self.assertEqual(live, [item])
        self.assertEqual(tracked, [item['metadata']])


if __name__ == '__main__': unittest.main()
