from reachy_mini import ReachyMini

with ReachyMini(host="192.168.50.216", connection_mode="network") as mini:
    print("Going to sleep...")
    mini.goto_sleep()
    print("Asleep.")
