import time

import numpy as np

from reachy_mini import ReachyMini
from reachy_mini.utils import create_head_pose

NEUTRAL_HEAD = create_head_pose()


def run(mini: ReachyMini, label: str, **kwargs):
    print(f"-> {label}")
    mini.goto_target(**kwargs)
    time.sleep(kwargs.get("duration", 0.5) + 0.3)


with ReachyMini() as mini:
    run(mini, "antennas up", antennas=np.deg2rad([45, 45]), duration=1.0)
    run(mini, "antennas down", antennas=np.deg2rad([-45, -45]), duration=1.0)
    run(mini, "antennas neutral", antennas=[0.0, 0.0], duration=1.0)

    run(mini, "head up 10mm", head=create_head_pose(z=10, mm=True), duration=1.0)
    run(mini, "head down 10mm", head=create_head_pose(z=-10, mm=True), duration=1.0)
    run(mini, "head tilt (roll)", head=create_head_pose(roll=15), duration=1.0)
    run(mini, "head nod (pitch)", head=create_head_pose(pitch=15), duration=1.0)
    run(mini, "head turn (yaw)", head=create_head_pose(yaw=20), duration=1.0)
    run(mini, "head neutral", head=NEUTRAL_HEAD, duration=1.0)

    run(mini, "body yaw left", body_yaw=np.deg2rad(30), duration=1.5)
    run(mini, "body yaw right", body_yaw=np.deg2rad(-30), duration=1.5)
    run(mini, "body yaw neutral", body_yaw=0.0, duration=1.5)

    run(
        mini,
        "combo move",
        head=create_head_pose(z=10, mm=True, yaw=15),
        antennas=np.deg2rad([30, -30]),
        body_yaw=np.deg2rad(15),
        duration=2.0,
        method="cartoon",
    )
    run(
        mini,
        "back to neutral",
        head=NEUTRAL_HEAD,
        antennas=[0.0, 0.0],
        body_yaw=0.0,
        duration=1.5,
    )

print("Done.")
