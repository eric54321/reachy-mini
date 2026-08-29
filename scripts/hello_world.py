from reachy_mini import ReachyMini

with ReachyMini() as mini:
    mini.goto_target(antennas=[0.5, -0.5], duration=0.5)
