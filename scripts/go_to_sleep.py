from reachy_mini import ReachyMini

with ReachyMini() as mini:
    print("Going to sleep...")
    mini.goto_sleep()
    print("Asleep.")
