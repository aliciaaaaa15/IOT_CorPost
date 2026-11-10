

## 1. App and settings

**App: Sensor Logger** (Kelvin Choi). It is free, available for iOS and Android, records accelerometer and gyroscope at the same time and exports as "Zipped CSV", which is the free format. Do not use "Combined CSV", which is paid.

| Setting | Value |
|---|---|
| Active sensors | **Accelerometer** and **gyroscope** only. Turn off GPS, camera, microphone, etc. |
| Sampling rate | **50 Hz** for both (or the highest the phone allows, if lower). The code later downsamples to 10 Hz. |
| Acceleration | The one that **includes gravity**. It is what makes it possible to compute the angle. The converter warns if the magnitude at rest is not ~1 g. |
| Screen | Always on, with the app in the foreground. |
| Interruptions | Airplane mode and "do not disturb", **with no vibration**. A vibration from a notification contaminates the data. |
| Battery | Turn off battery saving. |
| Phone | Use **the same phone** for everything. iOS and Android axes differ, and so do the sensors. |

## 2. Where and how to place the phone

First find out where the clip will go and replicate that. If it is not decided yet, use this position:

- **Area**: center of the chest, just below the collarbones (5-10 cm below the neck).
- **Orientation**: vertical, top side up and screen facing outward. It must always be identical.
- **Fastening**: a chest harness or elastic band for phones, or a very tight pocket. **Nothing that dangles**, such as a cord.
- **Fastening test**: walk and jump gently. If the phone bounces relative to the body, it is badly fastened and will create motion that the real clip will not have.

**Variety**, which is what makes the model generalize:
- At least 2 sessions on different days, with different clothing (thin T-shirt, sweatshirt).
- Take the phone off and put it back on between sessions.
- Use at least 2 different chairs, for example an office chair with wheels and a fixed one.
- At least 3 people, preferably 4-5, with different heights and builds. Ask permission from anyone taking part.

## 3. Procedure for each recording

1. Put on the phone, open the app and press **Start**.
2. For **5 s**, get into position and stay still in the initial posture. The code trims those seconds.
3. Do the activity for **120 s** (minimum 90 s). Use a **separate** clock or timer, not the phone.
4. In the final **5 s**, calmly take off the phone and press **Stop**.
5. Rename the recording and export it.

It is better if someone else presses Start/Stop and keeps the stopwatch.

**Why 120 s:** with 2 s windows and 50 % overlap, a recording gives about 110 windows. Many 2-minute recordings are better than a few 10-minute ones, because they give more variety of postures and repositioning.

## 4. Labeling rules (decide them now)

Print this and do not change it afterwards:

- **Valid**: trunk and shoulders still. Only hands, forearms, head, breathing and voice move.
- **Not valid**: the trunk, the shoulders or the whole body moves.
- **Changing posture** (from straight to slouched, repositioning) is not valid while it is being done. Once still in the new posture, it is valid.
- **A posture held still** is always valid, even if it is "bad": leaning, slouched, sideways.
- **A single activity per recording.** Do not change posture in the valid ones.
- **No long pauses** in the not-valid ones: if there is a stop of more than 1 s, those windows end up mislabeled. Do the cycles continuously.

## 5. What to record and how

The ones marked with ★ are the **core** (19 recordings, about 40 min per person). The full set is 30 recordings, a little over an hour per person.

The class names (first token of each file name) are Spanish prefixes and must be kept as they are: `run_own.py` uses them to assign the label.

### Valid (name starts with `sentado` or `depie`)

| Name | Rec. | How to do it |
|---|---|---|
| ★ `sentado_recto` | 2 | Straight back resting on the backrest, feet on the floor. Look at the screen, type and use the mouse normally. |
| ★ `sentado_encorvado` | 2 | Drooping shoulders, head forward, rounded back. It is the typical "bad" posture. |
| ★ `sentado_adelante` | 1 | Trunk leaning ~20-30° forward, elbows on the desk. |
| `sentado_reclinado` | 1 | Reclined backward on the backrest, ~20°. |
| `sentado_ladoizq` / `sentado_ladoder` | 1+1 | Trunk leaning ~10-15° to one side, resting on the armrest. |
| ★ `sentado_teclear` | 2 | Normal work: typing, mouse, looking at the screen, with natural micro-movements and without changing posture. |
| `sentado_movil` | 1 | Looking at the phone or reading on paper, head down. |
| `sentado_hablar` | 1 | Talking, drinking from a glass, scratching the face, coughing, laughing. Trunk still. |
| ★ `depie_quieto` | 1 | Standing still, weight evenly distributed. |

### Not valid (the first token is the class)

| Name | Rec. | How to do it |
|---|---|---|
| ★ `andar_normal` | 1 | Walk at a normal pace around the room or the corridor, with turns. |
| ★ `andar_lento` | 1 | Very slow walk, short steps. It is a difficult case. |
| ★ `levantarse_normal` | 1 | Continuous cycle: sitting, standing up, staying standing, sitting down. About 5-6 s per cycle. |
| ★ `levantarse_lento` | 1 | The same, very slowly, about 8-10 s per cycle. It is the borderline case identified in the design document. |
| ★ `estirar_delante` | 1 | Sitting, reach for an object 40-60 cm beyond the comfortable distance, come back, alternate hands. About 4 s per repetition. |
| `estirar_lado` | 1 | Reach for something at the side, at shoulder height. |
| `estirar_arriba` | 1 | Stretch with the arms up, yawn. |
| ★ `girar_tronco` | 1 | Sitting, rotate the torso 90° to the left and right, as if looking at someone behind. |
| `girar_silla` | 1 | Turn with the swivel chair from side to side. |
| ★ `agacharse_sentado` | 1 | Sitting, lean toward the floor to pick something up and come back, in cycles of ~5 s. |
| `agacharse_depie` | 1 | Standing, bend down to pick something up. |
| ★ `gesticular` | 1 | Sitting, explain something aloud with wide arm gestures. |
| ★ `inclinarse_normal` | 1 | Go from straight to slouched and back in cycles of ~3 s, without stopping. |
| ★ `inclinarse_lento` | 1 | The same but very slowly, about 6 s per cycle. It is another difficult case. |
| ★ `moverse_silla` | 1 | Reposition on the chair, move forward or backward, lean. |
| `moverse_piernas` | 1 | Cross and uncross the legs, rest a foot on the chair. |
| `moverse_chaqueta` | 1 | Put on and take off a jacket over and over. |

**More recordings:** the design document proposed 15-20 min per class and person. This version is a reduced one. If the results with the core set are promising, extend mainly the difficult cases (`levantarse_lento`, `inclinarse_lento`, `andar_lento`, `moverse_*`).

## 6. Naming and preparing the data

**Name format:** `class_detail_person_nn`, all lowercase, with no accents or spaces, and with no underscores inside each part.

Examples: `sentado_recto_ana_01.zip`, `levantarse_lento_luis_02.zip`. The **person** is the second-to-last block and is the one the code uses to leave someone out during validation.

Steps:

1. Export each recording as **Zipped CSV** and transfer it to the computer.
2. Rename each zip as above. The name becomes the label.
3. Convert and check the warnings:
   ```bash
   python convert_sensorlogger.py --src ./exportaciones --out ./mis_grabaciones
   ```
   Each line shows `OK` or `REVIEW`, with the duration, the actual sampling rate (it should be around 50 Hz), whether the acceleration is in m/s² or g, whether the magnitude at rest is ~1 g and whether there is a gyroscope.
4. Train and evaluate:
   ```bash
   python run_own.py --data ./mis_grabaciones --out ./out_own --orientation-free
   ```

**Nothing else needs to be done to the data.** Do not remove gravity, do not filter it, do not trim it by hand (the code already trims 5 s at each end) and do not normalize it. Keep the original zips as a backup.

