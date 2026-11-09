"""
convert_sensorlogger.py - Convierte exportaciones de Sensor Logger (zip con un CSV por
sensor) a un único CSV por grabación que entiende run_own.py, y comprueba su calidad.

Uso:
    python convert_sensorlogger.py --src ./exportaciones --out ./mis_grabaciones

--src: carpeta con los .zip exportados (o con carpetas ya descomprimidas).
       El NOMBRE del zip pasa a ser el nombre de la grabación, así que renombradlo
       ANTES de convertir:  sentado_recto_ana_01.zip
       Si la app añade la fecha al nombre (sentado_recto_ana_01-2026-10-08_21-26-20.zip)
       no hace falta quitarla: el conversor la elimina solo.

Salida: <nombre>.csv con columnas time_s, acc_x, acc_y, acc_z, gyro_x, gyro_y, gyro_z
        (acc tal como la entrega la app: m/s² o g; run_own.py lo detecta y convierte).
"""
import argparse, glob, io, os, re, zipfile
import numpy as np
import pandas as pd

# Sufijo de fecha/hora que añade la descarga: -2026-10-08_21-26-20 (y, si existe, lo que venga detrás,
# p. ej. " (1)" de un navegador al repetir descargas).
DATE_SUFFIX = re.compile(r"[-_ ]*\d{4}-\d{2}-\d{2}[ _T-]\d{2}[-:.]\d{2}[-:.]\d{2}.*$")


def clean_name(raw):
    """sentado_recto_alicia_01-2026-10-08_21-26-20 -> sentado_recto_alicia_01"""
    return DATE_SUFFIX.sub("", raw).strip()


def _read_sensor(files, keywords, exclude=("uncal", "raw")):
    """Busca en files (dict nombre_minúsculas -> bytes/ruta) el CSV del sensor."""
    for name, src in files.items():
        base = os.path.basename(name)
        if not base.endswith(".csv"):
            continue
        if any(k in base for k in keywords) and not any(e in base for e in exclude):
            return pd.read_csv(src), base
    return None, None


def _axis_cols(df):
    low = {c.lower(): c for c in df.columns}
    t = low.get("seconds_elapsed")
    if t is None:
        raise ValueError(f"Sin columna seconds_elapsed. Columnas: {list(df.columns)}")
    return t, [low[a] for a in "xyz"]


def convert_one(src_path, out_dir):
    """Convierte una exportación y devuelve el nombre limpio de la grabación (o None si falla)."""
    raw_name = os.path.splitext(os.path.basename(src_path.rstrip("/\\")))[0]
    name = clean_name(raw_name)
    files = {}
    if os.path.isdir(src_path):
        for p in glob.glob(os.path.join(src_path, "**", "*"), recursive=True):
            files[p.lower()] = p
    else:
        z = zipfile.ZipFile(src_path)
        for n in z.namelist():
            files[n.lower()] = io.BytesIO(z.read(n))

    acc, acc_name = _read_sensor(files, ["totalacceleration"])
    gyr, gyr_name = _read_sensor(files, ["gyroscope"])
    if acc is None:
        print(f"[ERROR] {raw_name}: no hay TotalAcceleration.csv. Archivos: "
              f"{[os.path.basename(k) for k in files][:15]}")
        return None
    ta, ca = _axis_cols(acc)
    t = acc[ta].to_numpy(float)
    A = acc[ca].to_numpy(float)

    if gyr is not None:
        tg, cg = _axis_cols(gyr)
        tgv = gyr[tg].to_numpy(float)
        G = np.column_stack([np.interp(t, tgv, gyr[c].to_numpy(float)) for c in cg])
    else:
        G = np.zeros_like(A)
        print(f"[AVISO] {name}: sin giroscopio; las características del giroscopio serán 0")

    out = pd.DataFrame(np.column_stack([t, A, G]),
                       columns=["time_s", "acc_x", "acc_y", "acc_z",
                                "gyro_x", "gyro_y", "gyro_z"])
    os.makedirs(out_dir, exist_ok=True)
    out.to_csv(os.path.join(out_dir, name + ".csv"), index=False)

    # ---- Comprobaciones de calidad ----
    dt = np.diff(t)
    fs = 1 / np.median(dt)
    dur = t[-1] - t[0]
    mag = np.linalg.norm(A, axis=1)
    unit = "m/s²" if np.median(mag) > 3 else "g"
    mag_g = mag / 9.80665 if unit == "m/s²" else mag
    msgs = []
    if fs < 40: msgs.append(f"frecuencia baja ({fs:.0f} Hz): subid la frecuencia en la app")
    if (dt > 0.1).sum() > 0: msgs.append(f"{(dt > 0.1).sum()} huecos > 0,1 s en los datos")
    if np.median(mag_g) < 0.5: msgs.append("la magnitud en reposo no es ~1 g: el sensor NO incluye "
                                           "gravedad (usad el sensor con gravedad / aceleración total)")
    if dur < 60: msgs.append(f"grabación corta ({dur:.0f} s)")
    status = "OK " if not msgs else "REVISAR"
    print(f"[{status}] {name}: {dur:5.0f} s | {fs:5.1f} Hz | acc en {unit} "
          f"(|a| mediana {np.median(mag_g):.2f} g) | gyro {'sí' if gyr is not None else 'NO'}"
          + ("" if not msgs else " | " + "; ".join(msgs)))
    return name


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--out", default="./mis_grabaciones")
    a = ap.parse_args()
    items = sorted(glob.glob(os.path.join(a.src, "*.zip")) +
                   [d for d in glob.glob(os.path.join(a.src, "*")) if os.path.isdir(d)])
    if not items:
        print("No encuentro .zip ni carpetas en", a.src); return
    seen = {}   # nombre limpio -> exportación original que lo generó
    for it in items:
        raw = os.path.splitext(os.path.basename(it.rstrip("/\\")))[0]
        # Si dos exportaciones dan el mismo nombre limpio (grabaste dos veces la misma),
        # la última (la de fecha más reciente, por orden alfabético) sobrescribe a la anterior.
        clean = clean_name(raw)
        if clean in seen:
            print(f"[AVISO] '{raw}' y '{seen[clean]}' dan el mismo nombre '{clean}': "
                  f"se conserva la última. Renombrad una de las dos si queréis las dos.")
        try:
            if convert_one(it, a.out):
                seen[clean] = raw
        except Exception as e:
            print(f"[ERROR] {it}: {e}")


if __name__ == "__main__":
    main()