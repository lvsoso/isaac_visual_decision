window.addEventListener('load',()=>{
 const checks=[];const check=(name,value)=>{if(!value)throw Error(name);checks.push(name);};
 try{
  check('CSP blocks network',document.querySelector('meta[http-equiv="Content-Security-Policy"]').content.includes("connect-src 'none'"));
  check('no model control',E.model_had_control===false&&document.body.textContent.includes('模型实际接管：False'));
  check('fourteen calls fourteen IDs',E.new_jev_verified_calls===14&&E.distinct_http_request_ids===14);
  check('failed admission',E.whole_pair_control_eligible===false);
  const sections=[...document.querySelectorAll('section')],images=[...document.images];
  check('sixteen sections',sections.length===16);check('fourteen audit images',images.length===14);
  let sectionIndex=0,imageIndex=0;
  for(const run of E.runs){
   const summary=sections[sectionIndex++];check(run.color+' five of seven',summary.querySelector('h2').textContent.includes('5/7'));
   check(run.color+' exact summary',JSON.stringify(JSON.parse(summary.querySelector('pre').textContent))===JSON.stringify(run.summary));
   for(const row of run.decisions){
    const s=sections[sectionIndex++],img=images[imageIndex++],name=run.color+row.index;
    check(name+' correct stage',s.querySelector('h3').textContent.includes('建议 '+row.proposed_action+' / 实际固定动作 '+row.expected_and_executed_action));
    check(name+' audit image exact',img.src==='data:image/png;base64,'+row.png_base64_audit_only&&img.naturalWidth===640&&img.naturalHeight===480);
    const tr=[...s.querySelectorAll('tr')].slice(1);check(name+' eight candidates',tr.length===8);
    check(name+' untouched probabilities',tr.every((r,index)=>r.children[0].textContent===Object.keys(row.probabilities)[index]&&Number(r.children[1].textContent)===Object.values(row.probabilities)[index]));
    const details=[...s.querySelectorAll('details')];
    for(const [index,key] of ['request','raw_http_body_text','http_meta','phase_outcome'].entries()){
     details[index].open=true;check(name+key+' exact',JSON.stringify(JSON.parse(details[index].querySelector('pre').textContent))===JSON.stringify(row[key]));
    }
    check(name+' text only',row.request.images.length===0&&row.request.state.camera_views.length===0);
   }
  }
  check('no horizontal overflow',document.body.scrollWidth<=innerWidth+1);
  check('no remote resources',performance.getEntriesByType('resource').every(r=>r.name.startsWith('data:')));
  const result=document.createElement('pre');result.id='ui-test-result';result.hidden=true;result.textContent=JSON.stringify({passed:true,check_count:checks.length,viewport:[innerWidth,innerHeight],checks,scope:'Offline report presentation only, no new API or Isaac/GPU run'});document.body.append(result);
 }catch(error){const result=document.createElement('pre');result.id='ui-test-result';result.textContent=JSON.stringify({passed:false,error:String(error),checks});document.body.append(result);}
});
