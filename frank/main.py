#!/usr/bin/env pybricks-micropython
from pybricks.hubs import EV3Brick
from pybricks.ev3devices import TouchSensor, Motor
from pybricks.parameters import Port, ImageFile, SoundFile
from pybricks.tools import wait
import random

# Initialize the EV3 brick.
ev3 = EV3Brick()

# Initialize the motors and button.
small_motor = Motor(Port.B)
large_motor = Motor(Port.C)

button = TouchSensor(Port.S1)

while True:
    ev3.screen.load_image(ImageFile.SLEEPING)

    # Play the snoring sound randomly
    while not button.pressed():
        wait_time = random.randint(1000, 3000)  # Random wait time between 1 and 3 seconds
        ev3.speaker.play_file(SoundFile.SNORING)
        wait(wait_time)

    ev3.screen.load_image(ImageFile.ANGRY)
    ev3.speaker.play_file(SoundFile.T_REX_ROAR)

    # Run the motors at different speeds. Adjust the speed values as needed.
    # The speed value can be between -1000 and 1000, where positive values run the motor forward
    # and negative values run it in reverse.
    small_motor.run(-500)  # Small motor runs at a medium speed.
    large_motor.run(1000)  # Large motor runs at a higher speed.

    # Keep the motors running for a specific duration (in milliseconds).
    wait(5000)

    # Stop the motors after the duration.
    small_motor.stop()
    large_motor.stop()