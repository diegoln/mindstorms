#!/usr/bin/env pybricks-micropython
"""
EV3D4 (LEGO MINDSTORMS EV3 R2-D2 bonus model) - with personality.
For LEGO EV3 MicroPython (Pybricks v2.0) on the EV3 Brick.

Wiring:
  Port A - Medium motor  (dome/head)
  Port B - Large motor   (right wheel)
  Port C - Large motor   (left wheel)
  Port 4 - Infrared sensor

What it does:
  * At start the head gently finds both of its end stops (low power),
    then centers. After that it never goes past those ends (minus a margin).
  * The head looks around at random by itself, all the time.
  * Remote on CHANNEL 1:
      - Left  red  up/down  -> left wheel forward/back
      - Right blue up/down  -> right wheel forward/back
      - BEACON button (top) -> FOLLOW MODE: head faces front (the IR sensor
        is on the dome) and R2 turns and drives toward the remote by himself.
        He learns which way to turn on his own (an "oops" beep = he flipped). Press BEACON again (or walk out of
        range) to go back to manual driving.
      - BOTH RED buttons (left up + left down) together -> DANCE
      - BOTH BLUE buttons (right up + right down) together -> TALK
  * When nobody drives him for a couple of seconds, he watches the IR sensor:
    put your hand (or anything) close in front and he gets SCARED - shrieks,
    shakes his head, backs away and turns off to the side.
  * Chirps and whistles every so often, happy sound when he finds the beacon,
    sad sound when he loses it.
  * Center button on the brick quits.
"""

from pybricks.hubs import EV3Brick
from pybricks.ev3devices import Motor, InfraredSensor
from pybricks.parameters import Port, Button, Direction, Stop, Color
from pybricks.tools import wait, StopWatch

try:
    from urandom import randint
except ImportError:
    from random import randint

# ------------------------------------------------------------------ settings
CHANNEL = 1

DRIVE_SPEED = 800            # deg/s for the wheels in manual mode
# The original ev3dev code runs the wheel motors with inverted polarity.
# If R2 drives backwards when you press "up", change to Direction.CLOCKWISE.
WHEEL_DIRECTION = Direction.COUNTERCLOCKWISE

# Head
CALIBRATE_HEAD = True        # find end stops at start. Set False to skip
                             # (then start with the dome facing front).
HEAD_CAL_DUTY = 35           # % motor power while finding end stops (keep low)
HEAD_CAL_TIMEOUT_MS = 6000   # no end stop found in this time -> free-spinning
HEAD_MARGIN = 20             # motor degrees to stay away from each end stop
HEAD_MIN_RANGE = 30          # warn if the usable +/- range is smaller than this
HEAD_RANGE_NO_CAL = 90       # +/- motor degrees used without end stops
HEAD_SPEED = 300             # deg/s for normal head moves
HEAD_MOVE_TIMEOUT_MS = 3000  # give up on a blocking head move after this
HEAD_LOOK_MIN_MS = 700       # random time between head moves
HEAD_LOOK_MAX_MS = 3000

# Follow mode
FOLLOW_DISTANCE = 25         # 0-100. Stops driving forward when this close.
FOLLOW_DRIVE_GAIN = 15       # forward speed per unit of distance
FOLLOW_TURN_GAIN = 8         # turn speed per degree of beacon angle
FOLLOW_MAX_SPEED = 700
FOLLOW_ANGLE_DEADBAND = 6    # degrees; ignore small angles to avoid wobble
# Which way to turn toward the beacon is learned automatically (see follow_step)
FOLLOW_GRACE_MS = 250        # keep driving through short beacon dropouts
FOLLOW_LOST_MS = 1200        # beacon gone this long -> back to manual
FOLLOW_COOLDOWN_MS = 1500    # wait after leaving follow before re-entering

# Scared (when idle and something comes close to the IR sensor)
SCARED_ENABLED = True
SCARED_DISTANCE = 30         # 0-100. Lower = you must come closer to scare him.
SCARED_IDLE_MS = 2000        # only gets scared after this long without driving
SCARED_CHECK_MS = 300        # how often to look for things nearby
SCARED_COOLDOWN_MS = 4000    # calm-down time before he can be scared again
SCARED_BACK_SPEED = 700
SCARED_BACK_MS = 700

# Sounds
IDLE_CHIRP_AFTER_MS = 4000   # only chirp on his own after this long idle
CHIRP_MIN_MS = 5000
CHIRP_MAX_MS = 12000
VOLUME = 70

# ------------------------------------------------------------------ hardware
ev3 = EV3Brick()
head = Motor(Port.A)
right = Motor(Port.B, WHEEL_DIRECTION)
left = Motor(Port.C, WHEEL_DIRECTION)
ir = InfraredSensor(Port.S4)
clock = StopWatch()
ev3.speaker.set_volume(VOLUME)


def clamp(x, lo, hi):
    return lo if x < lo else hi if x > hi else x


# ------------------------------------------------------------------ sounds
def chirp():
    """Random R2-style warble."""
    for _ in range(randint(3, 7)):
        ev3.speaker.beep(randint(1200, 4200), randint(25, 90))


def happy():
    for f in (1500, 2200, 3000, 3900):
        ev3.speaker.beep(f, 60)


def sad():
    for f in (2600, 2000, 1500, 1100, 800):
        ev3.speaker.beep(f, 110)


def whistle_up():
    for f in range(1000, 3600, 260):
        ev3.speaker.beep(f, 25)


# ------------------------------------------------------------------ head
HEAD_HALF = 0
next_look = 0
last_head_target = 0


def head_move_blocking(target, speed=HEAD_SPEED):
    """Move head to target and wait, but never forever and never pushing
    against something that holds it."""
    head.run_target(speed, target, Stop.HOLD, False)
    t = StopWatch()
    while abs(head.angle() - target) > 3:
        if head.control.stalled() or t.time() > HEAD_MOVE_TIMEOUT_MS:
            head.stop()
            return False
        wait(10)
    return True


def find_end_stop(direction):
    """Turn the head gently (low power) until it stops moving.
    Returns the angle, or None if it never stopped (free-spinning dome)."""
    head.dc(direction * HEAD_CAL_DUTY)
    t = StopWatch()
    wait(250)                      # let it get moving first
    still_since = None
    while t.time() < HEAD_CAL_TIMEOUT_MS:
        if abs(head.speed()) < 15:
            if still_since is None:
                still_since = t.time()
            elif t.time() - still_since > 150:
                head.stop()
                return head.angle()
        else:
            still_since = None
        wait(10)
    head.stop()
    return None


def calibrate_head():
    """Find both end stops, center the head, return safe half-range."""
    if not CALIBRATE_HEAD:
        head.reset_angle(0)
        return HEAD_RANGE_NO_CAL
    ev3.screen.clear()
    ev3.screen.print("Finding head...")
    a = find_end_stop(1)
    b = find_end_stop(-1) if a is not None else None
    if a is None or b is None:
        # No end stops: the dome turns freely, any range is safe.
        ev3.screen.print("No end stops")
        head.reset_angle(0)
        return HEAD_RANGE_NO_CAL
    half = max(abs(a - b) / 2 - HEAD_MARGIN, 0)
    head_move_blocking((a + b) / 2, 150)
    head.reset_angle(0)
    ev3.screen.print("Head +/- %d deg" % half)
    if half < HEAD_MIN_RANGE:
        ev3.screen.print("Range small!")
        ev3.screen.print("Check head gears")
        sad()
        wait(2000)
    return half


def head_look(frac, speed=HEAD_SPEED):
    """Point head at frac of its range: -1 = one end, 0 = front, 1 = other."""
    global last_head_target
    last_head_target = clamp(frac, -1, 1) * HEAD_HALF
    head.run_target(speed, last_head_target, Stop.HOLD, False)


def head_wander(now):
    """Random look-around. Sometimes a quick 'double take'."""
    global next_look
    if now < next_look:
        return
    r = randint(0, 9)
    if r < 2:
        head_look(0)                                   # look front
    elif r < 4:
        head_look(randint(-100, 100) / 100, HEAD_SPEED * 2)  # quick glance
    else:
        head_look(randint(-100, 100) / 100)
    next_look = now + randint(HEAD_LOOK_MIN_MS, HEAD_LOOK_MAX_MS)


def head_safety(now):
    """If something blocks the head, stop pushing and rest a moment."""
    global next_look
    if head.control.stalled():
        head.stop()
        next_look = now + 1500


# ------------------------------------------------------------------ driving
def run_or_stop(motor, fwd, back, speed):
    if fwd and not back:
        motor.run(speed)
    elif back and not fwd:
        motor.run(-speed)
    else:
        motor.stop()


def stop_wheels():
    left.stop()
    right.stop()


turn_sign = 1        # learned: which way to turn toward the beacon
check_at = 0
check_angle = 0
wrong_turns = 0


def follow_step(now, dist, angle):
    """Drive toward the beacon. The IR sensor is on the dome, so the head
    stays facing front while following and the body does the turning."""
    global turn_sign, check_at, check_angle, wrong_turns
    a = angle if abs(angle) >= FOLLOW_ANGLE_DEADBAND else 0

    # Self-learning turn direction: every 0.3 s, if the beacon is still on
    # the same side and drifted FURTHER off, we're turning the wrong way.
    # Three times in a row -> flip, with an "oops" beep.
    if now >= check_at:
        same_side = a * check_angle > 0
        drifting = abs(a) > abs(check_angle) + 5
        stuck_at_edge = abs(a) >= 70 and abs(check_angle) >= 70  # max is 75
        if same_side and (drifting or stuck_at_edge):
            wrong_turns += 1
            if wrong_turns >= 3:
                turn_sign = -turn_sign
                wrong_turns = 0
                ev3.speaker.beep(500, 120)
        else:
            wrong_turns = 0
        check_angle = a
        check_at = now + 300

    turn = FOLLOW_TURN_GAIN * a * turn_sign
    if a == 0:
        wrong_turns = 0
    fwd = FOLLOW_DRIVE_GAIN * (dist - FOLLOW_DISTANCE) if dist > FOLLOW_DISTANCE else 0
    if fwd == 0 and turn == 0:
        stop_wheels()
    else:
        left.run(clamp(fwd + turn, -FOLLOW_MAX_SPEED, FOLLOW_MAX_SPEED))
        right.run(clamp(fwd - turn, -FOLLOW_MAX_SPEED, FOLLOW_MAX_SPEED))


def follow_lost():
    """Beacon lost. If we were already drifting the wrong way, that's likely
    why: we turned until the beacon left the sensor's view. Flip for next time."""
    global turn_sign, wrong_turns, check_angle
    if wrong_turns > 0:
        turn_sign = -turn_sign
    wrong_turns = 0
    check_angle = 0


def something_close():
    """Two proximity readings in a row must both be close. The first reading
    after switching the sensor out of remote mode can be bogus."""
    if ir.distance() >= SCARED_DISTANCE:
        return False
    wait(30)
    return ir.distance() < SCARED_DISTANCE


# ------------------------------------------------------------------ screen
# R2-D2 front panel on the 178 x 128 screen:
#   top:    logic display (grid of blinking lights) + PSI light (round)
#   middle: vent bars on the left, slot panel + data port on the right
#   bottom: skirt stripes
LOGIC_COLS, LOGIC_ROWS = 12, 3
LOGIC_X, LOGIC_Y, CELL_W, CELL_H, CELL_GAP = 7, 7, 8, 7, 2
PSI_X, PSI_Y, PSI_R = 151, 19, 13
SCREEN_TICK_MS = 120

logic = [False] * (LOGIC_COLS * LOGIC_ROWS)
psi_on = False
next_screen = 0
next_psi = 0


def draw_cell(i, on):
    c, r = i % LOGIC_COLS, i // LOGIC_COLS
    x = LOGIC_X + c * (CELL_W + CELL_GAP)
    y = LOGIC_Y + r * (CELL_H + CELL_GAP)
    ev3.screen.draw_box(x, y, x + CELL_W - 1, y + CELL_H - 1,
                        fill=True, color=Color.BLACK if on else Color.WHITE)
    if not on:
        ev3.screen.draw_box(x, y, x + CELL_W - 1, y + CELL_H - 1)


def draw_psi(on):
    ev3.screen.draw_circle(PSI_X, PSI_Y, PSI_R - 3, fill=True,
                           color=Color.BLACK if on else Color.WHITE)
    ev3.screen.draw_circle(PSI_X, PSI_Y, PSI_R - 3)


def blink_random(n):
    """Flip n random logic lights."""
    for _ in range(n):
        i = randint(0, len(logic) - 1)
        logic[i] = not logic[i]
        draw_cell(i, logic[i])


def draw_body():
    s = ev3.screen
    s.clear()
    # logic display frame + PSI ring
    s.draw_box(3, 3, 127, 37, r=3)
    s.draw_circle(PSI_X, PSI_Y, PSI_R)
    s.draw_line(0, 43, 177, 43, 2)
    # vents
    for k in range(6):
        x = 10 + k * 12
        s.draw_box(x, 51, x + 5, 101, r=2, fill=True)
    # slot panel
    s.draw_box(88, 51, 168, 72, r=2)
    for y in (57, 62, 67):
        s.draw_line(94, y, 162, y, 2)
    # data port panel
    s.draw_box(88, 79, 168, 101, r=2)
    s.draw_box(95, 84, 125, 96, fill=True)
    s.draw_circle(146, 90, 6)
    s.draw_circle(146, 90, 2, fill=True)
    # skirt
    s.draw_line(0, 109, 177, 109, 2)
    s.draw_line(20, 115, 157, 115)
    s.draw_line(40, 121, 137, 121)
    for i in range(len(logic)):
        logic[i] = randint(0, 2) == 0
        draw_cell(i, logic[i])
    draw_psi(psi_on)


def screen_tick(now, mode):
    """Blink a few logic lights; PSI flickers (faster in follow mode)."""
    global next_screen, next_psi, psi_on
    if now >= next_screen:
        blink_random(3 if mode == "FOLLOW" else 2)
        next_screen = now + SCREEN_TICK_MS
    if now >= next_psi:
        psi_on = not psi_on
        draw_psi(psi_on)
        next_psi = now + (randint(120, 300) if mode == "FOLLOW"
                          else randint(300, 1200))


def logic_all(on):
    for i in range(len(logic)):
        logic[i] = on
        draw_cell(i, on)
    draw_psi(on)


# ------------------------------------------------------------------ tricks
def scared():
    """Shriek, shake head, back away, spin off a bit, then nervous mumble."""
    stop_wheels()
    for k, f in enumerate((4200, 2900, 4400, 2700, 4600, 2500)):
        if k % 2 == 0:
            logic_all(k % 4 == 0)
        ev3.speaker.beep(f, 35)
    for frac in (-0.7, 0.7, -0.5, 0.5):
        head_look(frac, HEAD_SPEED * 3)
        wait(120)
    head_look(0, HEAD_SPEED * 2)
    left.run(-SCARED_BACK_SPEED)
    right.run(-SCARED_BACK_SPEED)
    wait(SCARED_BACK_MS)
    d = 1 if randint(0, 1) else -1
    left.run(d * 400)
    right.run(-d * 400)
    wait(randint(300, 700))
    stop_wheels()
    wait(300)
    draw_body()
    for _ in range(randint(4, 6)):
        ev3.speaker.beep(randint(700, 1300), randint(40, 80))
        wait(40)


DANCE_NOTES = (1568, 2093, 1760, 2349, 1976, 2637, 2349, 3136)
DANCE_WIGGLE_SPEED = 500


def dance():
    """Wiggle left/right to a little tune, head swinging, lights flashing."""
    stop_wheels()
    for k, f in enumerate(DANCE_NOTES):
        d = 1 if k % 2 == 0 else -1
        left.run(d * DANCE_WIGGLE_SPEED)
        right.run(-d * DANCE_WIGGLE_SPEED)
        head_look(-d * 0.8, HEAD_SPEED * 3)
        logic_all(k % 2 == 0)
        ev3.speaker.beep(f, 180)
    # finale: quick spin with a happy warble
    left.run(700)
    right.run(-700)
    chirp()
    whistle_up()
    stop_wheels()
    head_look(0)
    draw_body()


def talk():
    """R2 'says' a few sentences: warbles, whistles, a raspberry, head bobs."""
    stop_wheels()
    for _ in range(randint(3, 5)):            # sentences
        head_look(randint(-60, 60) / 100, HEAD_SPEED * 2)
        kind = randint(0, 5)
        if kind == 0:                         # rising question whistle
            for f in range(1200, 3800, 200):
                ev3.speaker.beep(f, 20)
        elif kind == 1:                       # falling "oh no"
            for f in range(3400, 1000, -240):
                ev3.speaker.beep(f, 25)
        elif kind == 2:                       # grumpy raspberry
            for _ in range(8):
                ev3.speaker.beep(randint(180, 320), 30)
        else:                                 # chatter
            for _ in range(randint(4, 8)):
                ev3.speaker.beep(randint(1500, 4200), randint(25, 70))
        blink_random(4)                       # lights react while he talks
        draw_psi(randint(0, 1) == 1)
        head_look(0, HEAD_SPEED)              # little bob back to center
        wait(randint(150, 400))                # pause between sentences
    head_look(0)


def set_mode_light(mode):
    ev3.light.on(Color.ORANGE if mode == "FOLLOW" else Color.GREEN)


# ------------------------------------------------------------------ main
def main():
    global HEAD_HALF
    HEAD_HALF = calibrate_head()
    draw_body()
    whistle_up()
    set_mode_light("MANUAL")

    mode = "MANUAL"
    last_active = 0
    next_chirp = randint(CHIRP_MIN_MS, CHIRP_MAX_MS)
    last_seen = 0
    follow_allowed_at = 0
    next_scare_check = 0
    trick_latch = False

    while Button.CENTER not in ev3.buttons.pressed():
        now = clock.time()
        head_safety(now)
        screen_tick(now, mode)

        if mode == "MANUAL":
            pressed = ir.buttons(CHANNEL)

            if Button.BEACON in pressed and now >= follow_allowed_at:
                stop_wheels()
                mode = "FOLLOW"
                last_seen = now
                set_mode_light(mode)
                head_look(0)          # IR sensor is on the dome: face front
                happy()
                continue

            lu, ld = Button.LEFT_UP in pressed, Button.LEFT_DOWN in pressed
            ru, rd = Button.RIGHT_UP in pressed, Button.RIGHT_DOWN in pressed
            any_drive = lu or ld or ru or rd

            if (lu and ld) or (ru and rd):
                # Both red = dance, both blue = talk (these combos never drive)
                if not trick_latch:
                    if lu and ld:
                        dance()
                    else:
                        talk()
                    last_active = clock.time()
                    trick_latch = True
            elif trick_latch:
                # Wait until ALL buttons are released, so letting go of one
                # button a moment before the other doesn't twitch a wheel.
                stop_wheels()
                if not any_drive:
                    trick_latch = False
            else:
                run_or_stop(left, lu, ld, DRIVE_SPEED)
                run_or_stop(right, ru, rd, DRIVE_SPEED)
                if any_drive:
                    last_active = now

            head_wander(now)

            if (SCARED_ENABLED and not any_drive
                    and now - last_active > SCARED_IDLE_MS
                    and now >= next_scare_check):
                next_scare_check = now + SCARED_CHECK_MS
                if something_close():
                    scared()
                    last_active = clock.time()
                    next_scare_check = last_active + SCARED_COOLDOWN_MS
                    continue

            if now - last_active > IDLE_CHIRP_AFTER_MS and now >= next_chirp:
                chirp()
                next_chirp = clock.time() + randint(CHIRP_MIN_MS, CHIRP_MAX_MS)

        else:  # FOLLOW
            dist, angle = ir.beacon(CHANNEL)
            if dist is not None:
                last_seen = now
                follow_step(now, dist, angle)
            elif now - last_seen > FOLLOW_LOST_MS:
                stop_wheels()
                follow_lost()
                mode = "MANUAL"
                follow_allowed_at = now + FOLLOW_COOLDOWN_MS
                last_active = now
                set_mode_light(mode)
                head_look(0)
                sad()
            elif now - last_seen > FOLLOW_GRACE_MS:
                stop_wheels()
            # else: short dropout, keep doing what we were doing

        wait(20)


try:
    main()
finally:
    # Runs on normal exit AND if the program crashes or is stopped,
    # so R2 never drives off on his own.
    stop_wheels()
    try:
        head_move_blocking(0)
    finally:
        head.stop()
        ev3.light.on(Color.GREEN)
