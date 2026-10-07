(()=>{
 const checks=[];function check(n,c){if(!c)throw Error(n);checks.push(n);}
 try{
  check('eight rows including verified Jev',$('matrix-body').children.length===8);
  check('zero images in DOM',document.querySelectorAll('img').length===0);
  check('offline CSP',document.querySelector('meta[http-equiv="Content-Security-Policy"]').content.includes("connect-src 'none'"));
  check('new batch34 lifecycle',D.new_jev_run.lifecycle.complete&&D.new_jev_run.lifecycle.actual_transport_attempts===14&&D.new_jev_run.lifecycle.automatic_retries===0);
  check('correct new inference count',document.body.textContent.includes('28条既有Intern + 14条新Jev'));
  check('new basic policy',D.new_jev_run.lifecycle.validation_policy==='jev_sdk_basic_v1');
  for(const g of ['zh','en','jev']){
   check(g+' complete14',D.groups[g].summary.complete&&D.groups[g].summary.decisions.length===14);
   check(g+' no images',Object.values(D.groups[g].requests).every(r=>r.images.length===0&&r.state.camera_views.length===0));
  }
  for(const pair of ['binding','language','model'])for(const c of ['blue','yellow'])for(let s=1;s<=7;s++){
   $('pair').value=pair;$('color').value=c;$('stage').value=String(s);render();const [lo,hi]=PAIRS[pair],name=key(c,s),a=row(lo,name),b=row(hi,name);
   check(pair+c+s+' choices',$('choices').textContent==='参考 '+a.expected_action+'；'+a.proposed_action+' → '+b.proposed_action);
   check(pair+c+s+' probabilities',$('probabilities').children.length===8&&[...$('probabilities').children].every((tr,i)=>{const t=tr.children,x=D.actions[i];return t[1].textContent===pct(a.probabilities[x])&&t[2].textContent===pct(b.probabilities[x])&&t[3].textContent===pp(b.probabilities[x]-a.probabilities[x]);}));
   for(const [prefix,g] of [['low',lo],['high',hi]]){
    check(pair+c+s+prefix+' input exact',JSON.stringify(JSON.parse($(prefix+'-request').textContent))===JSON.stringify(request(g,name)));
    check(pair+c+s+prefix+' response exact',JSON.stringify(JSON.parse($(prefix+'-response').textContent))===JSON.stringify(response(g,name)));
   }
   check(pair+c+s+' selection',document.querySelectorAll('#matrix-body button[aria-pressed="true"]').length===1);
   if(pair==='model'){
    check(c+s+' same English inputs',JSON.stringify(request(lo,name))===JSON.stringify(request(hi,name)));
    const wire=JSON.parse($('wire-request').textContent),evidence=D.groups.jev.http_evidence[name];
    check(c+s+' actual wire matches',JSON.stringify(JSON.parse(evidence.actual_request_body_text))===JSON.stringify(wire));
    check(c+s+' raw response matches',JSON.stringify(JSON.parse(evidence.raw_response_body_text))===JSON.stringify(response(hi,name)));
    check(c+s+' raw saved before validation',evidence.metadata.status_code===200&&evidence.metadata.saved_before_business_validation);
    check(c+s+' confidence definitions separate',$('pair-scope').textContent.includes('confidence定义不同'));
   }
  }
  const downloads=[];download=(name,text,type)=>downloads.push({name,text,type});
  for(const g of ['zh','en','jev']){
   choose(g,'yellow',6);const name=key('yellow',6);$('download-request').click();$('download-response').click();const expected=g==='jev'?D.groups.jev.wire_requests[name]:request(g,name);
   check(g+' download input exact',JSON.stringify(JSON.parse(downloads[downloads.length-2].text))===JSON.stringify(expected));
   check(g+' download response exact',JSON.stringify(JSON.parse(downloads[downloads.length-1].text))===JSON.stringify(response(g,name)));
  }
  $('csv').click();const lines=downloads[downloads.length-1].text.trim().split('\n');check('CSV42actual rows',lines.length===43);check('CSV14pergroup',['zh','en','jev'].every(g=>lines.slice(1).filter(l=>l.startsWith(g+',')).length===14));
  $('theme').click();check('light theme',document.body.classList.contains('light'));$('theme').click();choose('jev','blue',6);
  check('no fullpage overflow',document.body.scrollWidth<=innerWidth+1);check('no external resources',performance.getEntriesByType('resource').length===0);
  const p=document.createElement('pre');p.id='ui-test-result';p.hidden=true;p.textContent=JSON.stringify({passed:true,check_count:checks.length,viewport:[innerWidth,innerHeight],checks,scope:'Offline presentation only; no new inference or Isaac/GPU physics'});document.body.append(p);
 }catch(e){const p=document.createElement('pre');p.id='ui-test-result';p.textContent=JSON.stringify({passed:false,error:String(e),checks});document.body.append(p);}
})();
