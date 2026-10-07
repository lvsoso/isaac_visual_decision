import concurrent.futures,html,json,re,subprocess,sys,tempfile,time
from pathlib import Path
from visual_lab.audit import write_json,sha256_file
root=Path('/private/var/folders/38/gc519q3j3p96d90ybwr3whvm0000gq/T/opencode/ivd-text-study-os9yxtix');report=Path(sys.argv[1]);output=Path(sys.argv[2]);folder=Path(tempfile.mkdtemp(prefix='ui-',dir=root));script=root/'ui_check.js';test=folder/'check.html'
test.write_text(report.read_text().replace('</body>','<script>'+script.read_text()+'</script></body>'));browser='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
def run(view):
 name,width=view;dom=folder/(name+'.dom.html');shot=folder/(name+'.png');args=[browser,'--headless','--no-first-run','--no-default-browser-check','--disable-gpu','--disable-background-networking','--disable-component-update','--user-data-dir='+str(folder/(name+'-profile')),'--window-size='+str(width)+',1100','--virtual-time-budget=12000','--screenshot='+str(shot),'--dump-dom',test.as_uri()];process=None
 try:
  with dom.open('w') as out,(folder/(name+'.stderr.log')).open('w') as err:
   process=subprocess.Popen(args,stdout=out,stderr=err);deadline=time.monotonic()+60
   while True:
    match=re.search(r'<pre id="ui-test-result"[^>]*>(.*?)</pre>',dom.read_text(),re.S)
    if match and shot.exists() and shot.stat().st_size>0:
     result=json.loads(html.unescape(match.group(1)));assert result['passed'],result;break
    assert process.poll() is None,'Browser exited before evidence completed'
    if time.monotonic()>deadline:raise TimeoutError(name)
    time.sleep(.25)
 finally:
  if process is not None and process.poll() is None:
   process.terminate()
   try:process.wait(timeout=10)
   except subprocess.TimeoutExpired:process.kill();process.wait(timeout=5)
 return name,result
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:results=dict(pool.map(run,[('desktop',1440),('narrow',500)]))
write_json(output,{'results':results,'fixture_dir':str(folder),'report_sha256':sha256_file(report),'check_script_sha256':sha256_file(script),'screenshots_sha256':{name:sha256_file(folder/(name+'.png')) for name in results},'driver_exit':'Closes only own isolated Chrome processes after page checks, DOM and screenshots.','new_model_inference':False,'gpu_physics_or_rendering_verified':False})
print(json.dumps({n:{k:v for k,v in r.items() if k!='checks'} for n,r in results.items()},indent=2))
