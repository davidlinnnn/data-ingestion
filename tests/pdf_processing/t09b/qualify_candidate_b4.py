"""Qualify the single-parser, 16-group T09b B4 diagnostic candidate."""
from qualify_baseline import qualify as qualify_run


def qualify(runtime, objects, controller):
    return qualify_run(runtime, objects, controller,
                       phase='t09b-calibration-b4', expected_groups=16,
                       expected_recycles=0, expected_generations=1,
                       expected_recycle_at=None)
