#!/usr/bin/env pybricks-micropython

# CHATGPT code below
from pybricks.ev3devices import TouchSensor
from pybricks.parameters import Port
from pybricks.tools import wait
from pybricks.hubs import EV3Brick

# Initialize the EV3 Brick.
ev3 = EV3Brick()

# Initialize the touch sensors.
touch_sensor_50 = TouchSensor(Port.S1)  # Sensor for R$0,50 coins
touch_sensor_100 = TouchSensor(Port.S2)  # Sensor for R$1,00 coins

# Initial amount
amount = 0.00

# Function to update the display
def update_display(amount):
    ev3.screen.clear()
    # Format the amount to always show two decimal places
    ev3.screen.draw_text(50, 60, "R${:.2f}".format(amount))

# Play start sound and show initial amount
ev3.speaker.beep()
update_display(amount)

# Main loop
while True:
    # Check if the touch sensor for R$0,50 coins is pressed
    if touch_sensor_50.pressed():
        amount += 0.50
        update_display(amount)
        while touch_sensor_50.pressed():  # Wait for the coin to be removed
            wait(10)

    # Check if the touch sensor for R$1,00 coins is pressed
    if touch_sensor_100.pressed():
        amount += 1.00
        update_display(amount)
        while touch_sensor_100.pressed():  # Wait for the coin to be removed
            wait(10)