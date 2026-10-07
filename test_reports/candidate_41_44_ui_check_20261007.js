window.addEventListener('load',()=>{
 const checks=[];const check=(name,value)=>{if(!value)throw Error(name);checks.push(name);};
 try{
  check('offline network CSP',document.querySelector('meta[http-equiv="Content-Security-Policy"]').content.includes("connect-src 'none'"));
  check('correct count and scope',document.body.textContent.includes('真实新推理 '+E.new_model_predictions+' 次')&&document.body.textContent.includes('低层目标仍来自配置'));
  check('Jev excluded',document.body.textContent.includes('Jev排除'));
  check('immutable new plan',E.plan.experiment_dir==='runs/41_44_intern_dual_experiment'&&E.plan.renewed_user_authorization===true);
  const sections=[...document.querySelectorAll('section')],images=[...document.images];
  const rows=E.runs.flatMap(r=>r.decisions||[]);check('ordered images count',images.length===2*rows.length);
  check('sections count',sections.length===E.runs.length+rows.length);
  let sectionIndex=0,imageIndex=0;
  for(const run of E.runs){
   const name=run.mode+'/'+run.color;const summary=sections[sectionIndex++];
   check(name+' summary exact',JSON.stringify(JSON.parse(summary.querySelector('pre').textContent))===JSON.stringify(run.summary||{}));
   for(const row of run.decisions||[]){
    const section=sections[sectionIndex++],stage=name+row.index;
    check(stage+' original choice and actual action',section.querySelector('h3').textContent.includes('模型 '+row.proposed_action+' · 执行 '+row.executed_action));
    for(const view of row.images){const image=images[imageIndex++];check(stage+view.path+' image exact',image.src==='data:image/png;base64,'+view.png_base64&&image.naturalWidth===640&&image.naturalHeight===480);}
    const tr=[...section.querySelectorAll('tr')].slice(1);check(stage+' eight candidates',tr.length===8);
    check(stage+' raw probabilities',tr.every((r,index)=>r.children[0].textContent===Object.keys(row.probabilities)[index]&&Number(r.children[1].textContent)===Object.values(row.probabilities)[index]));
    const details=[...section.querySelectorAll('details')];
    for(const [index,key] of ['request','response','phase_outcome','private_frozen_state'].entries()){
     details[index].open=true;check(stage+key+' exact',JSON.stringify(JSON.parse(details[index].querySelector('pre').textContent))===JSON.stringify(row[key]));
    }
    check(stage+' dual input',row.request.images.length===2&&row.request.state.camera_views.length===2);
    if(run.mode==='control')check(stage+' no answer reselection',row.proposed_action===row.executed_action);
   }
  }
  check('no page horizontal overflow',document.body.scrollWidth<=innerWidth+1);
  check('no external resources',performance.getEntriesByType('resource').every(r=>r.name.startsWith('data:')));
  const result=document.createElement('pre');result.id='ui-test-result';result.hidden=true;result.textContent=JSON.stringify({passed:true,check_count:checks.length,viewport:[innerWidth,innerHeight],checks,scope:'Offline report UI only, no extra model or Isaac execution'});document.body.append(result);
 }catch(error){const result=document.createElement('pre');result.id='ui-test-result';result.textContent=JSON.stringify({passed:false,error:String(error),checks});document.body.append(result);}
});
