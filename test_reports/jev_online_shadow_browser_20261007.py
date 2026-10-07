"""Check saved HTML in own isolated Chrome profiles, without inference or Isaac."""
import concurrent.futures,html,json,re,subprocess,tempfile,time
from pathlib import Path
from visual_lab.audit import write_json,sha256_file

ROOT=Path(__file__).resolve().parents[1]
report=ROOT/'docs/reports/jev_online_shadow_20261007.html';script=ROOT/'test_reports/jev_online_shadow_ui_check_20261007.js'
payload=ROOT/'test_reports/jev_online_shadow_20261007.json'
folder=Path(tempfile.mkdtemp(prefix='jev-online-ui-',dir='/private/var/folders/38/gc519q3j3p96d90ybwr3whvm0000gq/T/opencode'));page=folder/'check.html'
# Only the temporary test copy permits this injected script; delivered HTML has no scripts.
text=report.read_text().replace("connect-src 'none'","connect-src 'none'; script-src 'unsafe-inline'")
page.write_text(text.replace('</body>','<script>const E='+payload.read_text().replace('<','\\u003c')+';'+script.read_text()+'</script></body>'))
def run(view):
    name,width=view;dom=folder/(name+'.dom.html');shot=folder/(name+'.png')
    command=['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome','--headless','--no-first-run','--no-default-browser-check','--disable-gpu','--disable-background-networking','--disable-component-update','--user-data-dir='+str(folder/(name+'-profile')),'--window-size='+str(width)+',1100','--virtual-time-budget=12000','--screenshot='+str(shot),'--dump-dom',page.as_uri()]
    process=None
    try:
        with dom.open('w') as out,(folder/(name+'.stderr.log')).open('w') as err:
            process=subprocess.Popen(command,stdout=out,stderr=err);deadline=time.monotonic()+60
            while True:
                match=re.search(r'<pre id="ui-test-result"[^>]*>(.*?)</pre>',dom.read_text(),re.S)
                if match and shot.exists() and shot.stat().st_size>0:
                    result=json.loads(html.unescape(match.group(1)));assert result['passed'],result;break
                assert process.poll() is None,'Browser exited before result'
                if time.monotonic()>deadline:raise TimeoutError(name)
                time.sleep(.25)
    finally:
        if process is not None and process.poll() is None:
            process.terminate()
            try:process.wait(timeout=10)
            except subprocess.TimeoutExpired:process.kill();process.wait(timeout=5)
    return name,result
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:results=dict(pool.map(run,[('desktop',1440),('narrow',500)]))
write_json(ROOT/'test_reports/jev_online_shadow_ui_verified_20261007.json',{'results':results,'fixture_dir':str(folder),'report_sha256':sha256_file(report),'payload_sha256':sha256_file(payload),'check_script_sha256':sha256_file(script),'screenshots_sha256':{name:sha256_file(folder/(name+'.png')) for name in results},'new_model_inference':False,'gpu_physics_or_rendering_verified_by_browser':False,'delivered_html_scripts':0,'driver_exit':'Only own isolated Chrome processes closed; no user sessions touched'})
print(json.dumps({name:{k:v for k,v in result.items() if k!='checks'} for name,result in results.items()},indent=2))
