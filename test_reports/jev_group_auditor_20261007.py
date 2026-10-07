"""Independent offline audit of34Jev against frozen inputs and31EnglishIntern."""
import argparse,csv,datetime,json,math,re,statistics
from decimal import Decimal
from pathlib import Path
from visual_lab.audit import sha256_file,write_json
from visual_lab.core import ACTIONS
from visual_lab.goal_binding import binding_code_hashes
from visual_lab.jev import jev_payload,verify_jev_response
from visual_lab.jev_diagnostic import audit_choice_response

def audit(report,jev,wire,frozen,lifecycle,sdk,output,csv_output):
    data=json.loads(re.search(r'<script id="report-data" type="application/json">(.*?)</script>',report.read_text(),re.S).group(1))
    freeze=json.loads(frozen.read_text());life=json.loads(lifecycle.read_text());official=json.loads(sdk.read_text())
    groups=data['groups'];bundle=groups['jev'];summary=bundle['summary'];manifest=bundle['manifest'];final=bundle['final_health']
    assert summary['complete'] and summary['api_completed']==14 and not summary['mock_backend'] and summary['model_had_control'] is False
    assert life['complete'] and life['api_completed']==life['http_prediction_attempts']==life['actual_transport_attempts']==14
    assert life['automatic_retries']==0 and life['old32batch_resumed'] is False
    assert datetime.datetime.fromisoformat(freeze['frozen_utc'])<datetime.datetime.fromisoformat(life['started_utc'])
    assert sha256_file(frozen)==life['frozen_sha256']==data['new_jev_run']['frozen_manifest_sha256']
    assert binding_code_hashes()==freeze['code_sha256']==manifest['source_sha256']
    assert manifest['model_health']['validation_policy']==final['validation_policy']==life['validation_policy']=='jev_sdk_basic_v1'
    assert manifest['model_health']['requests_completed']==0 and final['requests_completed']==final['http_prediction_attempts']==14
    assert [r['name'] for r in summary['decisions']]==[j['name'] for j in freeze['planned_order']]
    expected=set(freeze['requests']);assert len(expected)==14 and {p.name for p in wire.iterdir()}==expected
    assert official['count']==14 and official['offline_parse_only'] and official['new_inference_calls']==0
    official_by_name={r['name']:r for r in official['checks']};results=[];matrix=[]
    english={r['name']:r for r in groups['en']['summary']['decisions']}
    for r in summary['decisions']:
        name=r['name'];path=wire/name;canonical=json.loads((jev/'requests'/(name+'.json')).read_text());request_body=(path/'request.body').read_bytes();raw_body=(path/'response.body').read_bytes()
        raw=json.loads(raw_body);meta=json.loads((path/'response_meta.json').read_text());marker=json.loads((path/'CALL_STARTED.json').read_text());original=json.loads((jev/'responses'/(name+'.json')).read_text())
        assert canonical==freeze['requests'][name]==groups['en']['requests'][name]==groups['jev']['requests'][name]
        assert canonical['images']==canonical['state']['camera_views']==[] and tuple(canonical['questions']['next_stage']['criteria'])==ACTIONS
        assert json.loads(request_body)==jev_payload(canonical)==freeze['wire_requests'][name]==bundle['wire_requests'][name]
        assert sha256_file(path/'request.body')==freeze['http_body_sha256'][name]
        assert sha256_file(jev/'requests'/(name+'.json'))==r['request_sha256']==manifest['planned_request_sha256'][name]==freeze['english_intern_request_sha256'][name]
        assert meta['status_code']==200 and meta['saved_before_business_validation'] and meta['body_sha256']==sha256_file(path/'response.body')
        assert marker['name']==name and marker['automatic_retries']==0
        assert raw==original==bundle['responses'][name] and sha256_file(jev/'responses'/(name+'.json'))==r['response_sha256']
        parsed=verify_jev_response(raw);answer=raw['answers']['next_stage'];assert parsed.action==r['proposed_action']==answer['choice']
        assert parsed.probabilities==r['probabilities']==answer['probabilities'] and parsed.confidence==r['confidence']==answer['confidence']
        assert r['expected_action']==english[name]['expected_action']==ACTIONS[r['decision_id']-1]
        assert official_by_name[name]['sdk_parse_success'] and official_by_name[name]['body_sha256']==meta['body_sha256']
        assert all(official_by_name[name][k] for k in ['probabilities_unchanged','choice_unchanged','confidence_unchanged'])
        numerical=audit_choice_response(raw);assert numerical['project_valid'] and not numerical['normalization_applied']
        results.append({'name':name,'request_id':meta['request_id'],'wire_request_sha256':sha256_file(path/'request.body'),
            'raw_response_sha256':meta['body_sha256'],'probability_sum_decimal':str(sum((Decimal(str(v)) for v in answer['probabilities'].values()),Decimal(0))),
            'current_basic_validation_passed':True,'informational_numeric_audit':numerical,'raw_http_response_text':raw_body.decode(),
            'raw_http_request_text':request_body.decode(),'metadata':meta,'usage':raw['usage']})
        matrix.append({'color':r['cell'].split('_')[0],'stage':r['decision_id'],'reference':r['expected_action'],'intern_choice':english[name]['proposed_action'],
            'jev_choice':r['proposed_action'],'intern_reference_probability':english[name]['probabilities'][r['expected_action']],
            'jev_reference_probability':r['probabilities'][r['expected_action']],'jev_confidence':r['confidence'],'jev_request_id':meta['request_id'],
            **{'jev_'+a:r['probabilities'][a] for a in ACTIONS},**{'intern_'+a:english[name]['probabilities'][a] for a in ACTIONS}})
    comparisons=[]
    for color in ['blue','yellow']:
        rows=sorted([r for r in matrix if r['color']==color],key=lambda r:r['stage']);intern_mean=statistics.mean(r['intern_reference_probability'] for r in rows);jev_mean=statistics.mean(r['jev_reference_probability'] for r in rows)
        comparisons.append({'color':color,'num_states':7,'intern_reference_agreement':sum(r['intern_choice']==r['reference'] for r in rows),
            'jev_reference_agreement':sum(r['jev_choice']==r['reference'] for r in rows),'intern_choices':[r['intern_choice'] for r in rows],
            'jev_choices':[r['jev_choice'] for r in rows],'intern_reference_probability_mean':intern_mean,'jev_reference_probability_mean':jev_mean,
            'reference_probability_delta_percentage_points':100*(jev_mean-intern_mean),'states':rows})
        assert next(c for c in summary['cells'] if c['color']==color)['baseline_agreement']==comparisons[-1]['jev_reference_agreement']
    for g in ['zh','en']:
        assert groups[g]['summary']['complete'] and groups[g]['summary']['api_completed']==14
    assert len({r['request_id'] for r in results})==14
    write_json(output,{'complete':True,'independently_verified':True,'new_jev_inference_count':14,'reused_intern_inference_count':28,'total_completed_comparison_rows':42,
        'old_failed32_and_diagnostic33_excluded':True,'api_retries':0,'mock_responses':0,'new_isaac_process_started':False,'model_had_control':False,
        'current_validation_policy':'jev_sdk_basic_v1','actual_response_model':'jev-1.13.0','lifecycle':life,'freeze_sha256':sha256_file(frozen),
        'canonical_english_pair_identical_count':14,'wire_body_hash_verified_count':14,'raw_response_preserved_before_validation_count':14,
        'official_sdk_offline_parse_count':14,'unique_http_request_id_count':14,'http_200_count':14,'comparisons':comparisons,'decisions':results,
        'token_usage_total':{k:sum(r['usage'][k] for r in results) for k in ['input_tokens','output_tokens']},
        'confidence_formula_tolerance_legacy_failures_informational_only':sum(abs(r['informational_numeric_audit'].get('confidence_formula_error',0))>.001 for r in results),
        'groups':groups,'scope':'Fixed-executor trajectory suggestion agreement, not autonomous success/calibration/significance. Seven correlated states; vendor APIs/precision and confidence definitions differ. Intern28historical, Jev14new; no pure-single-run claim.'})
    matrix.sort(key=lambda r:(r['color'],r['stage']))
    with csv_output.open('x',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(matrix[0]));writer.writeheader();writer.writerows(matrix)
    return comparisons

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ['report','jev','wire','frozen','lifecycle','sdk','output','csv_output']:parser.add_argument('--'+name.replace('_','-'),type=Path,required=True)
    args=parser.parse_args();print(json.dumps(audit(**vars(args)),ensure_ascii=False,indent=2))
