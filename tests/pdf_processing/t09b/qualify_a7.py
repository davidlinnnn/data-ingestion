"""Qualify the A7 group-5 matched baseline."""
from qualify_baseline import qualify as qualify_run


def qualify(runtime, objects, controller):
    return qualify_run(runtime, objects, controller,
                       phase='t09b-calibration-a7', expected_groups=29,
                       expected_recycles=1, expected_generations=2,
                       expected_recycle_at=20)
