#!/usr/bin/env pybricks-micropython

"""
Example LEGO® MINDSTORMS® EV3 Robot Arm Program
-----------------------------------------------

This program requires LEGO® EV3 MicroPython v2.0.
Download: https://education.lego.com/en-us/support/mindstorms-ev3/python-for-ev3

Building instructions can be found at:
https://education.lego.com/en-us/support/mindstorms-ev3/building-instructions#building-core
"""

from pybricks.hubs import EV3Brick
from pybricks.ev3devices import Motor, TouchSensor, ColorSensor, InfraredSensor
from pybricks.parameters import Port, Stop, Direction, Button
from pybricks.tools import wait

# Initialize the EV3 Brick
ev3 = EV3Brick()

# Configure the gripper motor on Port A with default settings.
gripper_motor = Motor(Port.A)

# Configure the elbow motor. It has an 8-teeth and a 40-teeth gear
# connected to it. We would like positive speed values to make the
# arm go upward. This corresponds to counterclockwise rotation
# of the motor.
elbow_motor = Motor(Port.B, Direction.COUNTERCLOCKWISE, [8, 40])

# Configure the motor that rotates the base. It has a 12-teeth and a
# 36-teeth gear connected to it. We would like positive speed values
# to make the arm go away from the Touch Sensor. This corresponds
# to counterclockwise rotation of the motor.
base_motor = Motor(Port.C, Direction.COUNTERCLOCKWISE, [12, 36])

# Limit the elbow and base accelerations. This results in
# very smooth motion. Like an industrial robot.
elbow_motor.control.limits(speed=60, acceleration=120)
base_motor.control.limits(speed=60, acceleration=120)

# Set up the Touch Sensor. It acts as an end-switch in the base
# of the robot arm. It defines the starting point of the base.
base_switch = TouchSensor(Port.S1)

# Set up the Color Sensor. This sensor detects when the elbow
# is in the starting position. This is when the sensor sees the
# white beam up close.
elbow_sensor = ColorSensor(Port.S3)

# Initialize the elbow. First make it go down for one second.
# Then make it go upwards slowly (15 degrees per second) until
# the Color Sensor detects the white beam. Then reset the motor
# angle to make this the zero point. Finally, hold the motor
# in place so it does not move.
elbow_motor.run_time(-30, 1000)
elbow_motor.run(15)
while elbow_sensor.reflection() < 32:
    wait(10)
elbow_motor.reset_angle(0)
elbow_motor.hold()

# Initialize the base. First rotate it until the Touch Sensor
# in the base is pressed. Reset the motor angle to make this
# the zero point. Then hold the motor in place so it does not move.
base_motor.run(-60)
while not base_switch.pressed():
    wait(10)
base_motor.reset_angle(0)
base_motor.hold()

# Initialize the gripper. First rotate the motor until it stalls.
# Stalling means that it cannot move any further. This position
# corresponds to the closed position. Then rotate the motor
# by 90 degrees such that the gripper is open.
gripper_motor.run_until_stalled(200, then=Stop.COAST, duty_limit=50)
gripper_motor.reset_angle(0)
gripper_motor.run_target(200, -90)

current_rotation = base_motor.angle()

# Constants
MIN_ARM_POSITION = base_motor.angle()
MAX_ARM_POSITION = base_motor.angle() + 180
MIN_ELBOW_POSITION = elbow_motor.angle() - 50
MAX_ELBOW_POSITION = elbow_motor.angle()
ARM_STEP = 10
ELBOW_STEP = 10        

# Configure the Infrared Sensor
ir_sensor = InfraredSensor(Port.S4)

def move_base(step):
    # Incrementally rotate the base motor, ensuring it stays within
    # [MIN_ARM_POSITION, MAX_ARM_POSITION].
    current_angle = base_motor.angle()
    target_angle = max(MIN_ARM_POSITION, min(MAX_ARM_POSITION, current_angle + step))
    base_motor.run_target(60, target_angle)

def move_elbow(step):
    # Incrementally rotate the elbow motor, ensuring it stays within
    # [MIN_ELBOW_POSITION, MAX_ELBOW_POSITION].
    current_angle = elbow_motor.angle()
    target_angle = max(MIN_ELBOW_POSITION, min(MAX_ELBOW_POSITION, current_angle + step))
    elbow_motor.run_target(60, target_angle)

def robot_pick():
    # This function makes the robot close the gripper and raise the elbow to
    # pick up the object.

    # Rotate to the pick-up position.
    #base_motor.run_target(60, position)
    # Lower the arm.
    #elbow_motor.run_target(60, -50)
    # Close the gripper to grab the wheel stack.
    gripper_motor.run_until_stalled(200, then=Stop.HOLD, duty_limit=50)
    # Raise the arm to lift the wheel stack.
    elbow_motor.run_target(60, 0)

def robot_release():
    # This function makes the open the gripper to release the object.
    # Then it raises its arm again.

    # Open the gripper to release the wheel stack.
    gripper_motor.run_target(200, -90)
    # Raise the arm.
    elbow_motor.run_target(60, 0)

# Play three beeps to indicate that the initialization is complete.
for i in range(3):
    ev3.speaker.beep()
    wait(100)

# Main loop
while True:
    # Get the remote control button states
    buttons = ir_sensor.buttons(channel=1)

    if Button.LEFT_UP in buttons:
        move_base(ARM_STEP)  # Rotate base clockwise
    elif Button.LEFT_DOWN in buttons:
        move_base(-ARM_STEP)  # Rotate base counterclockwise

    if Button.RIGHT_UP in buttons:
        robot_pick()
    elif Button.RIGHT_DOWN in buttons:
        move_elbow(-ELBOW_STEP)  # Lower the elbow

    if Button.BEACON in buttons:
        robot_release()  # Open the grip


    wait(100)