#!/usr/bin/env pybricks-micropython

# pybricks-micropython (EV3) — Seesaw, timed alternating (kick/curl), startup beep, post-prop baseline
# Motors: LEFT=A, RIGHT=D. Gyro: S1.

from pybricks.hubs import EV3Brick
from pybricks.ev3devices import Motor, GyroSensor
from pybricks.parameters import Port, Stop, Color
from pybricks.tools import wait

# =========================
# Ports
# =========================
LEFT_MOTOR_PORT  = Port.A
RIGHT_MOTOR_PORT = Port.D
GYRO_PORT        = Port.S1

# =========================
# Timing & power (metronome mode)
# =========================
HALF_CYCLE_MS        = 1200   # time for one phase: right kicks + left curls, then swap
KICK_DURATION_MS     = 700    # how long the kicker pushes
CURL_DURATION_MS     = 420    # how long the other side retracts (keeps from hyperextending)
KICK_SPEED_DPS       = 1360   # was 1700 — 20% less violent
CURL_SPEED_DPS       = 900

# Pre/post tiny resets to keep linkages free
PRE_RESET_MS         = 220     # brief retract before each kick
POST_CURL_EXTRA_MS   = 120     # small extra curl on the curling side (anti-stretch)

# =========================
# Bootstrap & baselines
# =========================
PROP_REMOVAL_BEEP_MS = 1000   # delay between beep and start of post-prop sampling
POST_PROP_SAMPLE_MS  = 400    # how long to average after prop is removed
POST_PROP_DT_MS      = 10

# =========================
# Stuck guard
# =========================
FLAT_BAND_DEG          = 2.0    # if |angle| <= this, considered flat
FLAT_CHECK_EVERY_MS    = 500
FLAT_STUCK_AFTER_MS    = 3500    # if flat that long, do untie
UNTIE_SPEED_DPS        = 700
UNTIE_TIME_MS          = 650

# =========================
# Logging
# =========================
DEBUG = False
ANGLE_LOG_EVERY_MS = 120

# =========================
# Setup
# =========================
ev3 = EV3Brick()
lm = Motor(LEFT_MOTOR_PORT)
rm = Motor(RIGHT_MOTOR_PORT)
gyro = GyroSensor(GYRO_PORT)

def clamp(x, lo, hi):
    return lo if x < lo else hi if x > hi else x

def read_angle(offset=0):
    return gyro.angle() - offset

def sample_mean_angle(ms, dt, offset_now=0):
    n = max(1, ms // dt)
    s = 0
    mn = +10**9
    mx = -10**9
    for _ in range(n):
        a = read_angle(offset_now)
        s += a
        if a < mn: mn = a
        if a > mx: mx = a
        wait(dt)
    return (s / n, mn, mx)

def untie_raw(tag="raw"):
    if DEBUG: print("  UNTIE({}): retract both legs ({} dps, {} ms)".format(tag, UNTIE_SPEED_DPS, UNTIE_TIME_MS))
    lm.run_time(-UNTIE_SPEED_DPS, UNTIE_TIME_MS, then=Stop.COAST, wait=False)
    rm.run_time(-UNTIE_SPEED_DPS, UNTIE_TIME_MS, then=Stop.COAST, wait=False)
    wait(UNTIE_TIME_MS + 60)

# --- Zero and initial sample (with prop) ---
ev3.light.on(Color.ORANGE)
gyro.reset_angle(0)
wait(800)
ev3.light.off()

if DEBUG:
    print("== Seesaw start (timed alternating, startup beep, NO AUDIO FILES) ==")
    print("Motors: LEFT=A, RIGHT=D; Gyro=S1")
    print("Gyro zeroed: angle={}°".format(gyro.angle()))

# Initial with-prop check (sanity)
m, mn, mx = sample_mean_angle(500, 10, 0)
if DEBUG:
    print("Initial (with prop) sample: mean={:.2f}°, min={}, max={}".format(m, int(mn), int(mx)))

# Beep: tell human to remove prop
if DEBUG:
    print("Beep: remove the prop now; establishing post-prop baseline in ~{} ms".format(PROP_REMOVAL_BEEP_MS))
ev3.speaker.beep(880, 120)
wait(PROP_REMOVAL_BEEP_MS)

# Post-prop baseline offset
ANGLE_OFFSET = 0
mean2, mn2, mx2 = sample_mean_angle(POST_PROP_SAMPLE_MS, POST_PROP_DT_MS, 0)
ANGLE_OFFSET = mean2
if DEBUG:
    print("Post-prop baseline set. mean={:.2f}°, min={}, max={}".format(ANGLE_OFFSET, int(mn2), int(mx2)))

# =========================
# Auto-calibrate directions (tiny pulses)
# =========================
def measure_delta_after_pulse(motor, speed_dps, dur_ms, expect_sign, label):
    a0 = read_angle(ANGLE_OFFSET)
    motor.run_time(speed_dps, dur_ms, then=Stop.COAST, wait=False)
    wait(dur_ms + 150)
    a1 = read_angle(ANGLE_OFFSET)
    d = a1 - a0
    if DEBUG:
        print("  {}: speed={} dps, dur={} ms -> Δ={:.2f}° (expect {})".format(
            label, speed_dps, dur_ms, d, "+" if expect_sign > 0 else "-"))
    return d

def auto_calibrate():
    if DEBUG: print("Calibrating directions...")
    untie_raw("cal")

    test_speed = 1200
    test_ms    = 220

    # RIGHT wants negative Δ when lifting right side
    d_r_pos = measure_delta_after_pulse(rm, +test_speed, test_ms, -1, "RIGHT +")
    untie_raw("cal")
    d_r_neg = measure_delta_after_pulse(rm, -test_speed, test_ms, -1, "RIGHT -")
    RIGHT_DIR = +1
    right_delta = d_r_pos
    if abs(d_r_neg) > abs(d_r_pos):
        RIGHT_DIR = -1
        right_delta = d_r_neg
    if right_delta > 0:  # enforce negative
        RIGHT_DIR *= -1
        right_delta = -right_delta

    # LEFT wants positive Δ when lifting left side
    untie_raw("cal")
    d_l_pos = measure_delta_after_pulse(lm, +test_speed, test_ms, +1, "LEFT +")
    untie_raw("cal")
    d_l_neg = measure_delta_after_pulse(lm, -test_speed, test_ms, +1, "LEFT -")
    LEFT_DIR = +1
    left_delta = d_l_pos
    if abs(d_l_neg) > abs(d_l_pos):
        LEFT_DIR = -1
        left_delta = d_l_neg
    if left_delta < 0:   # enforce positive
        LEFT_DIR *= -1
        left_delta = -left_delta

    if DEBUG:
        print("--- Calibration report ---")
        print("RIGHT_DIR={}, RIGHT Δ={:.2f}°".format(RIGHT_DIR, right_delta))
        print("LEFT_DIR={},  LEFT  Δ={:.2f}°".format(LEFT_DIR,  left_delta))
        print("KICK(ms,dps)=({}, {})  CURL(ms,dps)=({}, {})".format(
            KICK_DURATION_MS, KICK_SPEED_DPS, CURL_DURATION_MS, CURL_SPEED_DPS))
        print("--------------------------")
    return LEFT_DIR, RIGHT_DIR

LEFT_DIR, RIGHT_DIR = auto_calibrate()

# =========================
# Decide initial phase from current angle
# =========================
ang_now = read_angle(ANGLE_OFFSET)
# Phase A: RIGHT kicks + LEFT curls  | Phase B: LEFT kicks + RIGHT curls
phase_is_A = True if ang_now >= 0 else False  # if right is "down-ish", start by kicking right

if DEBUG:
    print("Entering metronome loop...")
    print("Start angle={:.2f}° -> phase {}".format(ang_now, "A (RIGHT kick / LEFT curl)" if phase_is_A else "B (LEFT kick / RIGHT curl)"))

# =========================
# Helpers for actions
# =========================
def do_kick(side_label, motor, dir_sign, tick_ms):
    # brief pre-reset to free linkages
    motor.run_time(-dir_sign * CURL_SPEED_DPS, PRE_RESET_MS, then=Stop.COAST, wait=False)
    wait(PRE_RESET_MS + 15)

    # main kick
    motor.run_time(dir_sign * KICK_SPEED_DPS, KICK_DURATION_MS, then=Stop.COAST, wait=False)
    if DEBUG:
        a0 = read_angle(ANGLE_OFFSET)
        print("[{} ms] KICK {}: dir={}, speed={} dps, dur={} ms, angle0={:.2f}°".format(
            tick_ms, side_label, dir_sign, KICK_SPEED_DPS, KICK_DURATION_MS, a0))

def do_curl(side_label, motor, dir_sign, tick_ms):
    # curl = retract (opposite the kick direction)
    motor.run_time(-dir_sign * CURL_SPEED_DPS, CURL_DURATION_MS, then=Stop.COAST, wait=False)
    wait(CURL_DURATION_MS + 10)
    # small extra curl to avoid hyperextension
    motor.run_time(-dir_sign * CURL_SPEED_DPS, POST_CURL_EXTRA_MS, then=Stop.COAST, wait=False)
    if DEBUG:
        a0 = read_angle(ANGLE_OFFSET)
        print("[{} ms] CURL {}: dir={}, speed={} dps, dur={}+{} ms, angle0={:.2f}°".format(
            tick_ms, side_label, -dir_sign, CURL_SPEED_DPS, CURL_DURATION_MS, POST_CURL_EXTRA_MS, a0))

# =========================
# Main metronome loop
# =========================
tick = 0
next_angle_log_ms = ANGLE_LOG_EVERY_MS
last_flat_mark_ms = 0
flat_since_ms = None

while True:
    # LED for rough state
    ang = read_angle(ANGLE_OFFSET)
    if abs(ang) <= FLAT_BAND_DEG:
        ev3.light.on(Color.ORANGE)
    elif ang > 0:
        ev3.light.on(Color.RED)      # right low-ish
    else:
        ev3.light.on(Color.GREEN)    # left low-ish

    # periodic angle log
    if DEBUG and tick >= next_angle_log_ms:
        print("[{} ms] angle={:.2f}°, phase={}".format(
            tick, ang, "A:Rkick Lcurl" if phase_is_A else "B:Lkick Rcurl"))
        next_angle_log_ms += ANGLE_LOG_EVERY_MS

    # --- one half-cycle ---
    start_ms = tick

    if phase_is_A:
        # RIGHT kicks, LEFT curls
        do_kick("RIGHT", rm, RIGHT_DIR, tick)
        do_curl("LEFT",  lm, LEFT_DIR,  tick)
    else:
        # LEFT kicks, RIGHT curls
        do_kick("LEFT",  lm, LEFT_DIR,  tick)
        do_curl("RIGHT", rm, RIGHT_DIR, tick)

    # Let the bounce happen for the remainder of the half-cycle
    elapsed = (HALF_CYCLE_MS - (tick - start_ms))
    if elapsed > 0:
        wait(elapsed)
        tick += elapsed
    else:
        # If our actions overran, just advance by a half-cycle to keep cadence
        tick += HALF_CYCLE_MS

    # Flat-stuck guard: check every FLAT_CHECK_EVERY_MS
    if (tick - last_flat_mark_ms) >= FLAT_CHECK_EVERY_MS:
        last_flat_mark_ms = tick
        ang_chk = read_angle(ANGLE_OFFSET)
        if abs(ang_chk) <= FLAT_BAND_DEG:
            if flat_since_ms is None:
                flat_since_ms = tick
            elif (tick - flat_since_ms) >= FLAT_STUCK_AFTER_MS:
                if DEBUG: print("[{} ms] FLAT-STUCK (|ang|={:.2f}°) -> UNTIE".format(tick, ang_chk))
                untie_raw("run")
                flat_since_ms = None
                # brief settle
                wait(200)
        else:
            flat_since_ms = None

    # Swap phase for next half-cycle
    phase_is_A = not phase_is_A
