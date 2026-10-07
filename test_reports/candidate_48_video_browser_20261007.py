"""Check actual local MP4 metadata and player layout; no Isaac/model."""
import concurrent.futures,html,json,re,subprocess,tempfile,time
from pathlib import Path
from visual_lab.audit import write_json,sha256_file

ROOT=Path(__file__).resolve().parents[1];page_path=ROOT/'docs/reports/candidate_48_video_20261007.html'
video_path=ROOT/'docs/videos/intern_dual_control_blue_20261007.mp4'
folder=Path(tempfile.mkdtemp(prefix='candidate-48-video-ui-',dir='/private/var/folders/38/gc519q3j3p96d90ybwr3whvm0000gq/T/opencode'))
text=page_path.read_text().replace("connect-src 'none'","connect-src 'none'; script-src 'unsafe-inline'")
for name in ['intern_dual_control_blue_20261007.mp4','intern_dual_control_blue_20261007.jpg']:
    text=text.replace('../videos/'+name,(ROOT/'docs/videos'/name).as_uri())
script="""<script>window.addEventListener('load',()=>{const checks=[];const check=(n,v)=>{if(!v)throw Error(n);checks.push(n)};const v=document.querySelector('video');try{
check('real MP4 metadata',v.videoWidth===640&&v.videoHeight===576&&Math.abs(v.duration-10.9)<.01);
check('native controls',v.controls);check('omitted API waits disclosed',document.body.textContent.includes('省略了暂停的API等待'));
check('supported H264 MP4',!!v.canPlayType('video/mp4; codecs="avc1.42E01E"'));check('no media error',!v.error);
check('no horizontal overflow',document.body.scrollWidth<=innerWidth+1);
const out=document.createElement('pre');out.id='video-check';out.hidden=true;out.textContent=JSON.stringify({passed:true,checks,viewport:[innerWidth,innerHeight]});document.body.append(out);
}catch(e){const out=document.createElement('pre');out.id='video-check';out.textContent=JSON.stringify({passed:false,error:String(e),checks});document.body.append(out)}});</script>"""
page=folder/'check.html';page.write_text(text.replace('</html>',script+'</html>'))
def run(view):
    name,width=view;dom=folder/(name+'.html');shot=folder/(name+'.png');process=None
    command=['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome','--headless','--no-first-run','--no-default-browser-check','--disable-gpu','--disable-background-networking','--disable-component-update','--autoplay-policy=no-user-gesture-required','--user-data-dir='+str(folder/(name+'-profile')),'--window-size='+str(width)+',1100','--virtual-time-budget=12000','--screenshot='+str(shot),'--dump-dom',page.as_uri()]
    try:
        with dom.open('w') as out,(folder/(name+'.stderr.log')).open('w') as err:
            process=subprocess.Popen(command,stdout=out,stderr=err);deadline=time.monotonic()+90
            while True:
                match=re.search(r'<pre id="video-check"[^>]*>(.*?)</pre>',dom.read_text(),re.S)
                if match and shot.exists() and shot.stat().st_size:
                    result=json.loads(html.unescape(match.group(1)));assert result['passed'],result;return name,result
                assert process.poll() is None,'Browser exited before video validation'
                if time.monotonic()>deadline:raise TimeoutError(name)
                time.sleep(.25)
    finally:
        if process is not None and process.poll() is None:
            process.terminate()
            try:process.wait(timeout=10)
            except subprocess.TimeoutExpired:process.kill();process.wait(timeout=5)
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:results=dict(pool.map(run,[('desktop',1440),('narrow',500)]))
write_json(ROOT/'test_reports/candidate_48_video_browser_verified_20261007.json',{'results':results,'video_sha256':sha256_file(video_path),'page_sha256':sha256_file(page_path),'fixture_dir':str(folder),'screenshots_sha256':{n:sha256_file(folder/(n+'.png')) for n in results},'delivered_page_scripts':0,'extra_model_or_gpu_calls':0,'headless_async_seek_play_not_verified':True,'prior_async_harness_attempts':'Two virtual-time dump-DOM attempts timed out before async result; no extra simulation or inference. Check now covers synchronous metadata/layout only; full decode was independently checked with FFmpeg.','scope':'Actual local MP4 metadata/codec/player layout; no full browser playback or simulator verification'})
print(json.dumps(results,indent=2))
