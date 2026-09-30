"""Qualify the single-parser, 16-group T09b B3 diagnostic candidate."""
from qualify_baseline import qualify as qualify_run


def qualify(runtime, objects, controller):
    return qualify_run(runtime, objects, controller,
                       phase='t09b-calibration-b3', expected_groups=16,
                       expected_recycles=0, expected_generations=1,
                       expected_recycle_at=None)
