"""Run from backend: python ../scripts/benchmark.py. Prints reproducible measured evidence."""
import sys,json,time,platform
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"backend"))
from app.energy import Config,synthetic,compare,PROFILES
from app.forecast import forecast
results={"python":platform.python_version(),"platform":platform.platform(),"seed":42,"cases":[]}
for profile,(_,solar,capacity) in PROFILES.items():
    cfg=Config(profile=profile,capacity=capacity,power=capacity*.4)
    frame=synthetic(profile,days=56)
    start=time.perf_counter();runs=compare(frame.iloc[-24:],cfg);elapsed=time.perf_counter()-start
    start=time.perf_counter();pred=forecast(frame);forecast_seconds=time.perf_counter()-start
    results["cases"].append({"profile":profile,"capacity_kwh":capacity,"solar_kw":solar,"dispatch_seconds":round(elapsed,3),"forecast_seconds":round(forecast_seconds,3),"strategies":{k:v["metrics"] for k,v in runs.items()},"forecast_metrics":pred["metrics"]})
print(json.dumps(results,indent=2))
