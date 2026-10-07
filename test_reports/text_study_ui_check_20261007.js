(()=>{
 const checks=[];function check(n,c){if(!c)throw Error(n);checks.push(n);}
 try{
  check('six matrix rows with no fabricated Jev rows',$('matrix-body').children.length===6);check('zero images in DOM',document.querySelectorAll('img').length===0);
  check('offline CSP',document.querySelector('meta[http-equiv="Content-Security-Policy"]').content.includes("connect-src 'none'"));
  check('Jev explicitly halted',!D.halted_jev.complete&&D.halted_jev.inference_attempts===1&&D.halted_jev.validated_decisions===0&&D.halted_jev.raw_response_retained===false);
  check('Jev raw probabilities absent',D.halted_jev.probability_values===null&&!('jev' in D.groups));
  check('model comparison unavailable',!document.querySelector('#pair option[value="model"]'));
  for(const group of ['zh','en']){
   check(group+' complete14',D.groups[group].summary.complete&&D.groups[group].summary.decisions.length===14);
   check(group+' zero image evidence',Object.values(D.groups[group].requests).every(r=>r.images.length===0&&r.state.camera_views.length===0));
  }
  for(const pair of ['binding','language'])for(const c of ['blue','yellow'])for(let s=1;s<=7;s++){
   $('pair').value=pair;$('color').value=c;$('stage').value=String(s);render();const [lo,hi]=PAIRS[pair],name=key(c,s),a=row(lo,name),b=row(hi,name);
   check(pair+c+s+' choices',$('choices').textContent==='参考 '+a.expected_action+'；'+a.proposed_action+' → '+b.proposed_action);
   check(pair+c+s+' probability table',$('probabilities').children.length===8&&[...$('probabilities').children].every((tr,i)=>{const t=tr.children,x=D.actions[i];return t[1].textContent===pct(a.probabilities[x])&&t[2].textContent===pct(b.probabilities[x])&&t[3].textContent===pp(b.probabilities[x]-a.probabilities[x]);}));
   for(const [prefix,g] of [['low',lo],['high',hi]]){
    check(pair+c+s+prefix+' request exact',JSON.stringify(JSON.parse($(prefix+'-request').textContent))===JSON.stringify(request(g,name)));
    check(pair+c+s+prefix+' response exact',JSON.stringify(JSON.parse($(prefix+'-response').textContent))===JSON.stringify(response(g,name)));
   }
   check(pair+c+s+' selected matrix cell',document.querySelectorAll('#matrix-body button[aria-pressed="true"]').length===1);
   if(pair==='model'){
    check(c+s+' English pair equality',JSON.stringify(request(lo,name))===JSON.stringify(request(hi,name)));
    const wire=JSON.parse($('wire-request').textContent);check(c+s+' actual Jev wire',!('images' in wire)&&wire.model==='jev-1.13.0'&&JSON.stringify(wire.state)===JSON.stringify(request(hi,name).state)&&JSON.stringify(wire.questions)===JSON.stringify(request(hi,name).questions));
    check(c+s+' Jev confidence separate',$('pair-scope').textContent.includes('confidence定义不同'));
   }
  }
  const downloads=[];download=(name,text,type)=>downloads.push({name,text,type});
  for(const group of ['zh','en']){choose(group,'yellow',6);const name=key('yellow',6);$('download-request').click();$('download-response').click();const got=JSON.parse(downloads[downloads.length-2].text),expected=request(group,name);
   check(group+' exact download request',JSON.stringify(got)===JSON.stringify(expected));check(group+' exact download response',JSON.stringify(JSON.parse(downloads[downloads.length-1].text))===JSON.stringify(response(group,name)));
  }
  $('csv').click();const lines=downloads[downloads.length-1].text.trim().split('\n');check('CSV28real data',lines.length===29);check('CSV14pergroup',['zh','en'].every(g=>lines.slice(1).filter(l=>l.startsWith(g+',')).length===14));
  $('theme').click();check('light theme toggle',document.body.classList.contains('light'));$('theme').click();choose('en','blue',6);
  check('no full page horizontal overflow',document.body.scrollWidth<=innerWidth+1);check('no resource request UI',performance.getEntriesByType('resource').length===0);
  const p=document.createElement('pre');p.id='ui-test-result';p.hidden=true;p.textContent=JSON.stringify({passed:true,check_count:checks.length,viewport:[innerWidth,innerHeight],checks,scope:'Presentation only, no model inference/Isaac GPU or physics validation'});document.body.append(p);
 }catch(e){const p=document.createElement('pre');p.id='ui-test-result';p.textContent=JSON.stringify({passed:false,error:String(e),checks});document.body.append(p);}
})();
