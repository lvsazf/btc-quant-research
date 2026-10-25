import copy, unittest
from test_signal_advice import run, fixtures, T, H

class Presentation(unittest.TestCase):
    def display(self, row):
        self.assertIn('presentation', row)
        return row['presentation']
    def test_wait_separates_target_and_action(self):
        p=self.display(run()['strategies']['ST'])
        self.assertEqual(p['target_text'],'策略目标：持仓')
        self.assertEqual(p['action_text'],'本轮无新增买卖建议')
        self.assertFalse(p['account_state_known'])
    def test_new_buy_preserved(self):
        p=self.display(run()['strategies']['T1']);self.assertEqual(p['action_text'],'建议买入做多')
    def test_cash_wait(self):
        s,_,_=fixtures();s['ST'].update(desired_state='CASH',previous_state='CASH')
        p=self.display(run(s)['strategies']['ST']);self.assertEqual(p['target_text'],'策略目标：空仓')
    def test_error_not_maintain(self):
        s,_,_=fixtures();s['ST']['event']='INVALID'
        p=self.display(run(s)['strategies']['ST']);self.assertEqual(p['kind'],'DATA_ERROR');self.assertNotIn('无新增',p['action_text'])
    def test_repeated_not_maintain(self):
        s,_,_=fixtures();p=self.display(run(previous={'signals':s,'signal_advice':run()})['strategies']['T1'])
        self.assertEqual(p['kind'],'REPEATED_RECONCILE_ORIGINAL_NOTIFICATION');self.assertIn('待核',p['action_text'])
    def test_historical_not_maintain(self):
        s,_,_=fixtures();s['ST'].update(desired_state='CASH',event='EXIT',incremental_orders=[dict(ts=T-H-1,side='sell',reason='STOP_INTRABAR')])
        p=self.display(run(s)['strategies']['ST']);self.assertEqual(p['kind'],'HISTORICAL_EVENTS_ONLY');self.assertIn('历史补算',p['action_text'])
    def test_initialization_not_trade(self):
        s,_,_=fixtures();s['ST'].update(previous_state=None,event='INITIALIZED')
        p=self.display(run(s)['strategies']['ST']);self.assertEqual(p['kind'],'INITIALIZED');self.assertIn('初始化',p['action_text'])
    def test_multi_event_order_not_hidden(self):
        s,_,_=fixtures();s['ST'].update(event='TRANSITIONS',incremental_orders=[dict(ts=T-1,side='sell',reason='STOP_INTRABAR'),dict(ts=T,side='buy',reason='ENTRY',signal_time=T)])
        p=self.display(run(s)['strategies']['ST']);self.assertEqual(p['action_text'],'建议买入做多');self.assertEqual([x['action'] for x in p['event_sequence']],['SELL_CLOSE_LONG','BUY_LONG']);self.assertEqual(p['event_sequence'][0]['event_status'],'SUPERSEDED_IN_INTERVAL')
    def test_gap_overrides_maintain(self):
        from signal_advice import build_advice
        s,t,m=fixtures();s['T1'].update(previous_target_state='LONG',event='WAIT',signal_available_utc=T+H)
        t['data'][0]['ts']=str(T+H+180000);m['received_utc']=T+H+180010
        p=self.display(build_advice(s,t,m,T+H+180020,'task',{'signals':{'T1':dict(signal_available_utc=T-H,target_state='CASH')}})['strategies']['T1'])
        self.assertEqual(p['kind'],'OBSERVATION_GAP');self.assertNotIn('无新增',p['action_text'])
    def test_missing_strategy_gets_error_display(self):
        s,_,_=fixtures();del s['ST'];p=self.display(run(s)['strategies']['ST']);self.assertEqual(p['target_text'],'策略目标：无法确认')
    def test_new_sell_preserved(self):
        s,_,_=fixtures();s['ST'].update(desired_state='CASH',event='EXIT',incremental_orders=[dict(ts=T-1,side='sell',reason='STOP_INTRABAR')])
        p=self.display(run(s)['strategies']['ST']);self.assertEqual(p['action_text'],'建议卖出平多');self.assertIsNone(p['event_sequence'][0]['signal_time_utc'])
    def test_presentation_is_non_mutating(self):
        from signal_advice import presentation
        row=run()['strategies']['T1'];old=copy.deepcopy(row);presentation(row);self.assertEqual(old,row)
    def test_unknown_event_never_maintain(self):
        from signal_advice import presentation
        p=presentation(dict(status='OK',target_state='LONG',action='MAINTAIN_LONG',new_action=False,events=[dict(action='BUY_LONG',event_status='UNKNOWN')]))
        self.assertEqual(p['kind'],'REVIEW_EVENTS')
