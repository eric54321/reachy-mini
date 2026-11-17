"""Reachy Mini inside the strands-robots library's simulation (no hardware).

    python scripts/robots_sim_reachy.py

Step 1 of the robotics learning path. It shows the library's three concepts on
Reachy's own MuJoCo model (shipped inside the reachy_mini package):

    Simulation  the world (MuJoCo, headless, runs far faster than real time)
    Robot       Reachy's body in that world: observe() and act()/run()
    Policy      a function  observation -> joint targets

Reachy's head is a Stewart platform: you don't set "head pitch", you set six leg
angles. strands-robots works in joint space, so we use the reachy_mini SDK's own
kinematics (AnalyticalKinematics) to turn a head pose into those six angles, and
forward kinematics to check what the simulated head actually did.

Joints the library sees: yaw_body, stewart_1..6, right_antenna, left_antenna.
"""

import math
from pathlib import Path

import numpy as np
import reachy_mini
from reachy_mini.kinematics.analytical_kinematics import AnalyticalKinematics
from reachy_mini.utils import create_head_pose
from scipy.spatial.transform import Rotation
from strands_robots import Robot

MJCF = Path(reachy_mini.__file__).parent / "descriptions" / "reachy_mini" / "mjcf" / "reachy_mini.xml"
HZ = 50
KIN = AnalyticalKinematics(automatic_body_yaw=False)


def head_targets(roll=0.0, pitch=0.0, yaw=0.0, body_yaw=0.0) -> dict:
    """Head pose in degrees -> the library's joint targets (body yaw + 6 Stewart legs)."""
    joints = KIN.ik(create_head_pose(roll=roll, pitch=pitch, yaw=yaw), body_yaw=body_yaw)
    names = ["yaw_body"] + [f"stewart_{i}" for i in range(1, 7)]
    return dict(zip(names, joints.tolist()))


def head_pose_from(obs) -> tuple[float, float, float]:
    """Observed joints -> (roll, pitch, yaw) of the head in degrees, via forward kinematics."""
    pos = dict(zip(obs.joints.names, obs.joints.positions))
    q = np.array([pos["yaw_body"]] + [pos[f"stewart_{i}"] for i in range(1, 7)])
    t = KIN.fk(q)
    return tuple(float(v) for v in Rotation.from_matrix(t[:3, :3]).as_euler("xyz", degrees=True))


def antennas(right_deg: float, left_deg: float) -> dict:
    return {"right_antenna": math.radians(right_deg), "left_antenna": math.radians(left_deg)}


# A tiny "choreography": (name, head pose in degrees, antennas in degrees, seconds)
MOVES = [
    ("look left", dict(yaw=25), (0, 0), 1.0),
    ("look right", dict(yaw=-25), (0, 0), 1.0),
    ("nod down", dict(pitch=15), (0, 0), 0.8),
    ("tilt head", dict(roll=15), (0, 0), 0.8),
    ("antennas out", dict(), (40, -40), 0.8),
    ("neutral", dict(), (0, 0), 0.8),
]


def make_policy(target: dict):
    """A Policy is just a function: observation -> joint targets. This one holds a pose."""

    def policy(obs):
        return target

    return policy


def main() -> None:
    robot = Robot(MJCF)  # joins Simulation.default(): a headless MuJoCo world
    print(f"Loaded '{robot.name}' with joints: {robot.description.joints}\n")
    print(f"{'move':<14}{'commanded (roll/pitch/yaw deg)':<34}{'simulated head':<30}antennas (R/L deg)")

    total_sim = 0.0
    for name, head, ant, seconds in MOVES:
        target = {**head_targets(**head), **antennas(*ant)}
        result = robot.run(make_policy(target), hz=HZ, seconds=seconds)
        total_sim += result.seconds
        obs = robot.observe()
        cmd = (head.get("roll", 0), head.get("pitch", 0), head.get("yaw", 0))
        got = head_pose_from(obs)
        pos = dict(zip(obs.joints.names, obs.joints.positions))
        ant_now = (math.degrees(pos["right_antenna"]), math.degrees(pos["left_antenna"]))
        print(
            f"{name:<14}{str(tuple(round(v) for v in cmd)):<34}"
            f"{str(tuple(round(v, 1) for v in got)):<30}"
            f"({ant_now[0]:.0f}, {ant_now[1]:.0f})"
        )
    print(f"\nSimulated {total_sim:.1f}s of robot time.")


if __name__ == "__main__":
    main()
