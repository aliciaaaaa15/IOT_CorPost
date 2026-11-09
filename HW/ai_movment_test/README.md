# Validez de medición - pipeline
1. pip install numpy pandas scikit-learn matplotlib
2. python run_hapt.py --data .  --out out                         # dataset HAPT (carpeta con RawData/)
   python run_hapt.py --data .  --out out_of --orientation-free   # sin características por eje
3. Grabar vuestros datos y: python run_own.py --data ./mis_grabaciones --orientation-free
4. Copiar out*/decision_tree.h + features.h al firmware.
Archivos: har_common.py (ventanas/características/baseline), run_hapt.py, run_own.py, features.h



5. Convertir los datos recolectados al formato del pipeline para poder ser procesados:
python convert_sensorlogger.py --src ./exportaciones --out ./mis_grabaciones

6. Generar, entrenar y evaluar el modelo basado en los datos recolectados:
python run_own.py --data ./mis_grabaciones --out ./out_own --orientation-free



7. Evaluar el rendimiento de los diferentes árboles creados al procesar nuestros datos recolectados:
python evaluate.py --data ./mis_grabaciones --models out/decision_tree.h out_orientation_free/decision_tree.h --in-sample-models out_own/decision_tree.h --out ./out_eval

Sin out_own tree:
python evaluate.py --data ./mis_grabaciones --models out/decision_tree.h out_orientation_free/decision_tree.h --out ./out_eval
