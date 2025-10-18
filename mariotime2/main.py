#!/usr/bin/env pybricks-micropython

# pybricks-micropython (EV3) — Mario Time Gate Controller
# Motor: Small motor on Port A (gate control)
# Color Sensor: Port S1 (detects red to close gate)

from pybricks.hubs import EV3Brick
from pybricks.ev3devices import Motor, ColorSensor
from pybricks.parameters import Port, Stop, Color
from pybricks.tools import wait
from pybricks.media.ev3dev import SoundFile
import random

# =========================
# Ports
# =========================
GATE_MOTOR_PORT = Port.A
COLOR_SENSOR_PORT = Port.S1

# =========================
# Gate Settings (CALIBRATE THIS VALUE)
# =========================
# To calibrate:
# 1. Run the program - it will find red (fully open) and set that as position 0
# 2. Watch the gate close and open repeatedly
# 3. Note the position printed in debug output when gate is closed
# 4. Adjust GATE_TRAVEL_DEGREES below to match the desired closed position
GATE_TRAVEL_DEGREES = 240  # Distance to close gate from red position - ADJUST THIS!

GATE_OPEN_SPEED = 200      # degrees per second to open gate
GATE_CLOSE_SPEED = 200     # degrees per second to close gate
INIT_SEARCH_SPEED = 50     # slow speed to search for red during initialization (gentle on robot)

# Color detection
RED_CHECK_INTERVAL_MS = 50  # how often to check for red color

# Dungeon sound effects (played randomly before gate closes)
DUNGEON_SOUNDS = [
    SoundFile.LAUGHING_1,   # Evil laugh
]

# =========================
# Debug
# =========================
DEBUG = False

# =========================
# Setup
# =========================
ev3 = EV3Brick()
gate_motor = Motor(GATE_MOTOR_PORT)
color_sensor = ColorSensor(COLOR_SENSOR_PORT)

# =========================
# Initialization
# =========================
def find_home_position():
    """
    Initialize by rotating motor until red is detected (fully open position).
    Sets this as position 0 (home/open position).
    """
    if DEBUG:
        print("=== INITIALIZING ===")
        print("Searching for fully open position (red)...")

    ev3.light.on(Color.ORANGE)

    # Start rotating to find red (fully open position)
    gate_motor.run(-INIT_SEARCH_SPEED)

    # Keep checking for red
    while True:
        detected_color = color_sensor.color()

        if detected_color == Color.RED:
            # Found red! This is fully open position
            gate_motor.stop()

            if DEBUG:
                print("Fully open position (RED) found!")

            # Reset motor angle to 0 (this is our open/home position)
            gate_motor.reset_angle(0)

            # Beep to confirm initialization complete
            ev3.speaker.beep(frequency=1000, duration=200)

            if DEBUG:
                print("Initialization complete. Position 0 set at RED (fully open)")

            ev3.light.on(Color.GREEN)
            wait(1000)  # Wait 1 second before starting cycle
            ev3.light.off()

            return

        wait(RED_CHECK_INTERVAL_MS)

# =========================
# Gate Control Functions
# =========================
def close_gate(travel_degrees):
    """Close the gate by rotating away from red position."""
    if DEBUG:
        print("Closing gate... ({} degrees from red)".format(travel_degrees))

    ev3.light.on(Color.ORANGE)

    # Rotate away from red (close the gate)
    gate_motor.run_angle(GATE_CLOSE_SPEED, travel_degrees, then=Stop.HOLD, wait=True)

    if DEBUG:
        print("Gate closed. Position: {} degrees".format(gate_motor.angle()))

def open_gate():
    """Open the gate by rotating back until red is detected."""
    current_position = gate_motor.angle()

    if DEBUG:
        print("Opening gate from {} degrees back to red...".format(current_position))

    ev3.light.on(Color.GREEN)

    # Start rotating back toward red (negative direction)
    gate_motor.run(-GATE_OPEN_SPEED)

    # Monitor for red color while opening
    while True:
        detected_color = color_sensor.color()

        if detected_color == Color.RED:
            # Stop immediately when red is detected
            gate_motor.stop()
            if DEBUG:
                print("RED detected! Gate stopped at {} degrees".format(gate_motor.angle()))

            # Reset to 0 for consistent position tracking
            gate_motor.reset_angle(0)
            break

        # Safety check: don't go past position 0
        if gate_motor.angle() <= 0:
            gate_motor.stop()
            if DEBUG:
                print("Position 0 reached (RED NOT DETECTED!)".format(gate_motor.angle()))
            break

        wait(RED_CHECK_INTERVAL_MS)

    if DEBUG:
        print("Gate open. Position: {} degrees".format(gate_motor.angle()))

def wait_for_red():
    """Wait until color sensor detects red."""
    if DEBUG:
        print("Waiting for RED color...")

    while True:
        detected_color = color_sensor.color()

        if detected_color == Color.RED:
            if DEBUG:
                print("RED detected!")
            ev3.speaker.beep(frequency=1000, duration=100)
            return

        wait(RED_CHECK_INTERVAL_MS)

# =========================
# Main Program
# =========================
def main():
    if DEBUG:
        print("=== MARIO TIME GATE CONTROLLER ===")
        print("Motor: Port A (small motor)")
        print("Color Sensor: Port S1")
        print()

    # Initialize - find home position (closed gate at red)
    find_home_position()

    if DEBUG:
        print()
        print("=== STARTING GATE CYCLE ===")
        print("Travel distance: {} degrees".format(GATE_TRAVEL_DEGREES))
        print()

    # Main loop
    cycle_count = 0
    while True:
        cycle_count += 1

        if DEBUG:
            print("--- Cycle {} ---".format(cycle_count))

        # Randomly play evil laugh before closing the gate (20% chance)
        if random.randint(0, 4) == 0:
            dungeon_sound = random.choice(DUNGEON_SOUNDS)
            ev3.speaker.play_file(dungeon_sound)

        # Close the gate (move away from red)
        close_gate(GATE_TRAVEL_DEGREES)

        # Pause while closed
        wait(1000)

        # Open the gate (return to red position at 0)
        open_gate()

        # Pause while open before next cycle
        ev3.light.on(Color.GREEN)
        wait(1000)
        ev3.light.off()

# =========================
# Run
# =========================
try:
    main()
except KeyboardInterrupt:
    if DEBUG:
        print()
        print("Program stopped by user")
    gate_motor.stop()
    ev3.light.off()
