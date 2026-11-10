# Measurement validity - pipeline
1. pip install numpy pandas scikit-learn matplotlib
2. python run_hapt.py --data .  --out out                         # HAPT dataset (folder containing RawData/)
   python run_hapt.py --data .  --out out_of --orientation-free   # without per-axis features
3. Record our own data and run: python run_own.py --data ./mis_grabaciones --orientation-free
4. Copy out*/decision_tree.h + features.h into the firmware.
Files: har_common.py (windows/features/baseline), run_hapt.py, run_own.py, features.h



5. Convert the collected data to the pipeline format so that it can be processed:
python convert_sensorlogger.py --src ./exportaciones --out ./mis_grabaciones

6. Generate, train and evaluate the model based on the collected data:
python run_own.py --data ./mis_grabaciones --out ./out_own --orientation-free



7. Evaluate the performance of the different trees created when processing our collected data:
python evaluate.py --data ./mis_grabaciones --models out/decision_tree.h out_orientation_free/decision_tree.h --in-sample-models out_own/decision_tree.h --out ./out_eval

Without the out_own tree:
python evaluate.py --data ./mis_grabaciones --models out/decision_tree.h out_orientation_free/decision_tree.h --out ./out_eval
