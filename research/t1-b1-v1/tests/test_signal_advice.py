import copy, json, sys, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from signal_advice import build_advice, H
T=1792368000000 # 2026-10-19 00 UTC

def fixtures():
    ticker={'code':'00000','data':[{'symbol':'BTCUSDT','lastPr':'82000','ts':str(T+180000)}]}
    meta={'http_status':200,'code':'00000','received_utc':T+180010,'url':'https://api.bitget.com/api/v2/mix/market/ticker'}
    # Numeric UTC input accepted for deterministic fixtures.
    daily=dict(target_state='LONG',previous_target_state='CASH',event='ENTER_LONG_TRANSITION',signal_available_utc=T,basis_daily_close_ms=T,indicators={'close':82000})
    st=dict(desired_state='LONG',previous_state='LONG',event='WAIT',signal_available_utc=T,incremental_orders=[])
    return {'T1':daily,'B1':copy.deepcopy(daily),'ST':st},ticker,meta

def run(signals=None,previous=None,checkpoint=None):
    s,t,m=fixtures()
    return build_advice(signals or s,t,m,T+180020,'task',previous,checkpoint)

class Advice(unittest.TestCase):
    def test_daily_entry(self):
        x=run()['strategies']['T1']; self.assertEqual(x['action'],'BUY_LONG');self.assertTrue(x['new_action']);self.assertEqual(x['events'][0]['reference_price'],82000)
    def test_daily_exit(self):
        s,_,_=fixtures();s['B1'].update(target_state='CASH',previous_target_state='LONG',event='EXIT_LONG_TRANSITION')
        self.assertEqual(run(s)['strategies']['B1']['action'],'SELL_CLOSE_LONG')
    def test_wait_has_no_quote_or_old_position(self):
        s,_,_=fixtures();s['T1'].update(previous_target_state='LONG',event='WAIT')
        x=run(s)['strategies']['T1'];self.assertEqual(x['action'],'MAINTAIN_LONG');self.assertEqual(x['events'],[])
        self.assertNotIn('position',json.dumps(x));self.assertNotIn('quantity',json.dumps(x))
    def test_initialized_not_buy(self):
        s,_,_=fixtures();s['ST'].update(previous_state=None,event='INITIALIZED')
        x=run(s)['strategies']['ST'];self.assertEqual(x['action'],'INITIALIZED_LONG');self.assertFalse(x['new_action'])
    def test_invalid_initial_orders(self):
        s,_,_=fixtures();s['ST'].update(previous_state=None,event='INITIALIZED',incremental_orders=[{'side':'buy'}])
        self.assertEqual(run(s)['strategies']['ST']['status'],'DATA_ERROR')
    def test_same_event_different_round_reconciles(self):
        s,_,_=fixtures();first=run();p={'signals':s,'signal_advice':first,'notification':'NOT_SUBMITTED'}
        x=run(previous=p)['strategies']['T1'];self.assertFalse(x['new_action']);self.assertTrue(x['repeated_event_ids']);self.assertIn('RECONCILE',x['events'][0]['event_status'])
        self.assertNotIn('SENT',json.dumps(x))
    def test_retry_same_inputs_same_event_id(self):
        self.assertEqual(run()['strategies']['T1']['events'][0]['event_id'],run()['strategies']['T1']['events'][0]['event_id'])
    def test_old_version_same_boundary_dedup(self):
        s,_,_=fixtures();x=run(previous={'signals':s})['strategies']['T1'];self.assertFalse(x['new_action'])
    def test_daily_skipped_boundary_not_wait(self):
        s,t,m=fixtures();s['T1'].update(previous_target_state='LONG',event='WAIT',signal_available_utc=T+H)
        p={'signals':{'T1':dict(signal_available_utc=T-H,target_state='CASH')}}
        t['data'][0]['ts']=str(T+H+180000);m['received_utc']=T+H+180010
        x=build_advice(s,t,m,T+H+180020,'task',p)['strategies']['T1'];self.assertEqual(x['status'],'OBSERVATION_GAP');self.assertEqual(x['action'],'REVIEW_MISSED_INTERVAL')
    def test_same_daily_basis_missing_hour_not_trade(self):
        s,t,m=fixtures();s['T1'].update(previous_target_state='LONG',event='WAIT',signal_available_utc=T+3*H)
        p={'signals':{'T1':dict(signal_available_utc=T+H,target_state='LONG')}}
        t['data'][0]['ts']=str(T+3*H+180000);m['received_utc']=T+3*H+180010
        x=build_advice(s,t,m,T+3*H+180020,'task',p)['strategies']['T1'];self.assertEqual(x['action'],'MAINTAIN_LONG');self.assertFalse(x['new_action'])
    def test_st_new_entry_current_quote_not_fill(self):
        s,_,_=fixtures();s['ST'].update(previous_state='CASH',event='ENTER',incremental_orders=[dict(ts=T,side='buy',signal_time=T,reason='ENTRY',fill=1,q=2,fee=0)])
        x=run(s)['strategies']['ST'];self.assertEqual(x['action'],'BUY_LONG');self.assertEqual(x['events'][0]['reference_price'],82000);self.assertNotIn('fill',x['events'][0])
    def test_intrabar_stop_has_interval_not_fake_time(self):
        s,_,_=fixtures();s['ST'].update(desired_state='CASH',event='EXIT',incremental_orders=[dict(ts=T-1,side='sell',reason='STOP_INTRABAR')])
        x=run(s)['strategies']['ST'];self.assertEqual(x['action'],'SELL_CLOSE_LONG');self.assertIsNone(x['events'][0]['signal_time_utc']);self.assertIsNotNone(x['events'][0]['signal_interval_end_utc'])
    def test_multi_event_final_state_not_hide_stop(self):
        s,_,_=fixtures();s['ST'].update(event='TRANSITIONS',incremental_orders=[dict(ts=T-1,side='sell',reason='STOP_INTRABAR'),dict(ts=T,side='buy',reason='ENTRY',signal_time=T)])
        x=run(s)['strategies']['ST'];self.assertEqual(len(x['events']),2);self.assertEqual(x['events'][0]['event_status'],'SUPERSEDED_IN_INTERVAL');self.assertEqual(x['action'],'BUY_LONG')
    def test_historical_catchup_not_new_signal(self):
        s,_,_=fixtures();s['ST'].update(desired_state='CASH',event='EXIT',incremental_orders=[dict(ts=T-H-1,side='sell',reason='STOP_INTRABAR')])
        x=run(s)['strategies']['ST'];self.assertFalse(x['new_action']);self.assertEqual(x['status'],'HISTORICAL_EVENTS_ONLY');self.assertNotIn('reference_price',x['events'][0])
    def test_bad_event_not_wait(self):
        s,_,_=fixtures();s['T1']['event']='WAIT';self.assertEqual(run(s)['strategies']['T1']['status'],'DATA_ERROR')
    def test_stale_quote_rejected(self):
        s,t,m=fixtures();t['data'][0]['ts']=str(T)
        with self.assertRaises(ValueError):build_advice(s,t,m,T+180020,'task')
    def test_future_quote_rejected(self):
        s,t,m=fixtures();t['data'][0]['ts']=str(T+200000)
        with self.assertRaises(ValueError):build_advice(s,t,m,T+180020,'task')
    def test_bad_price_rejected(self):
        for v in ('NaN','0','-3','Infinity'):
            s,t,m=fixtures();t['data'][0]['lastPr']=v
            with self.assertRaises(ValueError):build_advice(s,t,m,T+180020,'task')
    def test_input_immutable(self):
        s,t,m=fixtures();saved=copy.deepcopy((s,t,m));build_advice(s,t,m,T+180020,'task');self.assertEqual(saved,(s,t,m))
    def test_st_missing_branch_keeps_daily(self):
        s,_,_=fixtures();del s['ST'];r=run(s);self.assertEqual(r['strategies']['ST']['status'],'DATA_ERROR');self.assertEqual(r['strategies']['T1']['action'],'BUY_LONG')
    def test_daily_fraction_is_rule_cap(self):
        x=run()['strategies']['T1']['events'][0]['suggested_fraction'];self.assertEqual(x['value'],.9);self.assertEqual(x['basis'],'STRATEGY_AVAILABLE_CASH_FEE_INCLUSIVE_CAP')
    def test_exit_fraction_all_strategy_position(self):
        s,_,_=fixtures();s['T1'].update(target_state='CASH',previous_target_state='LONG',event='EXIT_LONG_TRANSITION');x=run(s)['strategies']['T1']['events'][0]['suggested_fraction'];self.assertEqual(x['value'],1);self.assertEqual(x['basis'],'EXISTING_STRATEGY_POSITION')
    def test_st_fraction_from_verified_position(self):
        s,_,_=fixtures();o=dict(ts=T,side='buy',signal_time=T,reason='ENTRY',fill=80000,q=.005,fee=.24);s['ST'].update(previous_state='CASH',event='ENTER',incremental_orders=[o]);cp={'ledger':{'position':dict(entry_time=T,initial_equity=1000,entry_fill=80000,q=.005,entry_fee=.24)}}
        x=run(s,checkpoint=cp)['strategies']['ST']['events'][0]['suggested_fraction'];self.assertAlmostEqual(x['value'],.40024)
    def test_st_fraction_no_basis_no_guess(self):
        s,_,_=fixtures();s['ST'].update(previous_state='CASH',event='ENTER',incremental_orders=[dict(ts=T,side='buy',signal_time=T,reason='ENTRY')]);x=run(s)['strategies']['ST']['events'][0]['suggested_fraction'];self.assertIsNone(x['value'])

    def test_bad_http_rejected(self):
        s,t,m=fixtures();m['http_status']=500
        with self.assertRaises(ValueError):build_advice(s,t,m,T+180020,'task')
    def test_adjacent_target_conflict(self):
        s,_,_=fixtures();p={'signals':{'T1':dict(signal_available_utc=T-H,target_state='LONG')}}
        self.assertEqual(run(s,previous=p)['strategies']['T1']['status'],'DATA_ERROR')
    def test_st_inverted_event_state(self):
        s,_,_=fixtures();s['ST'].update(event='ENTER',incremental_orders=[dict(ts=T,side='buy',reason='ENTRY')])
        self.assertEqual(run(s)['strategies']['ST']['status'],'DATA_ERROR')
    def test_future_signal_rejected_per_branch(self):
        s,_,_=fixtures();s['ST']['signal_available_utc']=T+H
        r=run(s);self.assertEqual(r['strategies']['ST']['status'],'DATA_ERROR');self.assertEqual(r['strategies']['T1']['status'],'OK')
    def test_old_closed_signal_rejected_per_branch(self):
        s,_,_=fixtures();s['ST']['signal_available_utc']=T-H
        self.assertEqual(run(s)['strategies']['ST']['status'],'DATA_ERROR')
    def test_st_fraction_mismatch_is_missing(self):
        s,_,_=fixtures();s['ST'].update(previous_state='CASH',event='ENTER',incremental_orders=[dict(ts=T,side='buy',reason='ENTRY',q=.005,fill=80000,fee=.24)])
        cp={'ledger':{'position':dict(entry_time=T-H,initial_equity=1000,q=.005,entry_fill=80000,entry_fee=.24)}}
        self.assertIsNone(run(s,checkpoint=cp)['strategies']['ST']['events'][0]['suggested_fraction']['value'])
    def test_archive_reader_requires_original_hash(self):
        import tempfile,hashlib
        from signal_advice import read_previous_decision
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);(p/'run').mkdir();content=json.dumps({'signals':{}})
            pack={'round_id':'r','files':{'decision.json':dict(content=content,bytes=len(content.encode()),sha256=hashlib.sha256(content.encode()).hexdigest())}}
            raw=json.dumps(pack).encode();(p/'google-evidence.json').write_bytes(raw)
            ref=dict(path=str(p/'run/st_checkpoint.json'),round_id='r',archive_sha256=hashlib.sha256(raw).hexdigest())
            self.assertEqual(read_previous_decision(ref),{'signals':{}})
            ref['archive_sha256']='bad'
            with self.assertRaises(ValueError):read_previous_decision(ref)
    def test_only_latest_multi_event_gets_current_quote(self):
        s,_,_=fixtures();s['ST'].update(event='TRANSITIONS',incremental_orders=[dict(ts=T-1,side='sell',reason='STOP_INTRABAR'),dict(ts=T,side='buy',reason='ENTRY')])
        events=run(s)['strategies']['ST']['events'];self.assertNotIn('reference_price',events[0]);self.assertIn('reference_price',events[1])

    def test_st_future_trigger_not_displayed(self):
        s,_,_=fixtures();s['ST'].update(previous_state='CASH',event='ENTER',incremental_orders=[dict(ts=T,signal_time=T+H,side='buy',reason='ENTRY')])
        self.assertEqual(run(s)['strategies']['ST']['status'],'DATA_ERROR')
    def test_archive_reader_rejects_wrong_identity(self):
        import tempfile,hashlib
        from signal_advice import read_previous_decision
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);(p/'run').mkdir();raw=json.dumps({'round_id':'other'}).encode();(p/'google-evidence.json').write_bytes(raw)
            ref=dict(path=str(p/'run/st_checkpoint.json'),round_id='r',archive_sha256=hashlib.sha256(raw).hexdigest())
            with self.assertRaises(ValueError):read_previous_decision(ref)

if __name__=='__main__':unittest.main()


