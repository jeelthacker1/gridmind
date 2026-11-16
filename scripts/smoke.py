"""Exercise the real Compose Redis worker and PostgreSQL persistence via HTTP."""
import json,os,time,urllib.request,http.cookiejar

base=os.getenv("BASE_URL","http://localhost:3000")
client=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
def request(path,body=None):
    data=None if body is None else json.dumps(body).encode()
    req=urllib.request.Request(base+"/api"+path,data=data,headers={"Content-Type":"application/json"})
    with client.open(req,timeout=30) as response:return json.load(response)

request("/login",{"email":"admin@gridmind.local","password":os.environ["DEMO_PASSWORD"]})
dataset=request("/datasets")[0]["id"]
rid=request("/runs",{"dataset_id":dataset})["id"]
for _ in range(90):
    run=request(f"/runs/{rid}")
    if run["status"]=="failed":raise RuntimeError(run["result"])
    if run["status"]=="complete":break
    time.sleep(1)
else:raise TimeoutError("Redis worker did not complete dispatch")
assert len(run["result"]["baseline"]["optimized"]["rows"])==24
print("Compose smoke passed: authenticated API, PostgreSQL datasets/results, Redis queued dispatch.")
