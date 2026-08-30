from reachy_mini import ReachyMini

with ReachyMini(host="192.168.50.216", connection_mode="network") as mini:
    mini.enable_motors()  # no-op if already on; commands silently do nothing without it
    print("Waking up...")
    mini.wake_up()
    print("Awake.")
