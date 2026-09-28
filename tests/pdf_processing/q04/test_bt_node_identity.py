"""The relocated worker must verify its own immutable node identity."""

import unittest
from unittest import mock

from sentinel import run_warm_pod_cgroup_bt as run


class NodeIdentityTest(unittest.TestCase):
    def test_worker1_identity_is_checked_before_admission(self):
        self.assertIs(run.base.run_outer_admission.__globals__["verify_outer_identity"],
                      run.verify_outer_identity_bt)

        class Kube:
            uid = "bfdeceea-67a2-4d7f-ac32-8b97efda6d71"
            boot = "c01b81ac-b0fd-4ce6-8cda-f0da74b9bbd3"
            pods = []

            def json(self, *args, **_kwargs):
                if args[:2] == ("get", "node"):
                    assert args[2] == run.topology.NODE
                    return {"metadata": {"uid": self.uid},
                            "status": {"nodeInfo": {"bootID": self.boot}}}
                assert args[:2] == ("get", "pods")
                return {"items": self.pods}

        kube = Kube()
        with mock.patch.object(run.base, "verify_held_deployments") as held:
            run.verify_outer_identity_bt(kube)
            held.assert_called_once_with(kube, deadline=None)
            kube.uid = "wrong"
            with self.assertRaisesRegex(ValueError, "node UID changed"):
                run.verify_outer_identity_bt(kube)
            kube.uid = "bfdeceea-67a2-4d7f-ac32-8b97efda6d71"
            kube.boot = "wrong"
            with self.assertRaisesRegex(ValueError, "node boot identity changed"):
                run.verify_outer_identity_bt(kube)
            kube.boot = "c01b81ac-b0fd-4ce6-8cda-f0da74b9bbd3"
            kube.pods = [{}]
            with self.assertRaisesRegex(ValueError, "owned worker Pod already exists"):
                run.verify_outer_identity_bt(kube)


if __name__ == "__main__":
    unittest.main()
