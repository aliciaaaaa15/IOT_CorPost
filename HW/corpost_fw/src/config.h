/* CorPost firmware parameters (PoC).
  The development values can be adjusted depending on what is being tested;
  the final values will be decided after testing. */
#pragma once

/* Sampling: 2 s window at 25 Hz (50 samples), as in D3 */
#define SAMPLE_PERIOD_MS     40
#define WINDOW_SAMPLES       50
#define MIN_VALID_SAMPLES    40   /* if more samples are lost over I2C, the window is INVALID */

/* Interval between measurements. Development: 15 s (D3: 1, 3 or 5 min).
  It is the initial value: the app can change it with command 0x01. */
#define MEASURE_INTERVAL_S     15
#define MEASURE_INTERVAL_MIN_S 5    /* limits accepted by command 0x01 */
#define MEASURE_INTERVAL_MAX_S 3600

/* Tolerance margin: deviation from the reference posture beyond which the
  posture is BAD. Initial value: the app changes it with command 0x02. */
#define TOLERANCE_DEG        15.0f
#define TOLERANCE_MIN_DEG    1      /* limits accepted by command 0x02 */
#define TOLERANCE_MAX_DEG    90

/* Circular reading buffer for BLE disconnections (D3: 50 readings) */
#define BUFFER_SIZE          50

/* "Battery" field of the packet. The PoC has no battery (USB): 0xFF = not available */
#define BATTERY_LEVEL        0xFF

/* PROVISIONAL motion filter: threshold on the standard deviation of the magnitude
  of the acceleration within the window (0.042 g = baseline of the HAPT pipeline).
  It will be replaced by the decision tree retrained at 25 Hz. */
#define MOTION_STD_MG        42.0f

/* Vibration: minimum time between two alerts. Development: 0 (vibrates on every BAD).
  D3: 300 s (5 min). */
#define VIB_MIN_INTERVAL_S   0
