import unittest
from copy import deepcopy
from decimal import Decimal
import engine as e
D=Decimal; H=3600000

def bar(h,o=100,hgh=101,l=99,c=100):
 return dict(ts=h*H,open=D(str(o)),high=D(str(hgh)),low=D(str(l)),close=D(str(c)),volume=D(1))
def candidate(d=1,t0=400*H,tp=110,sl=95,boundary=100):
 return dict(t0=t0,d=d,boundary=D(str(boundary)),p0=D(101),sl=D(str(sl)),tp=D(str(tp)),target_source=dict(center_time=390*H,confirmed_time=393*H,price=D(str(tp))))
def trend_rows(n=101):
 return [bar(j*4+k,100+j,101+j,99+j,100+j) for j in range(n) for k in range(4)]
def setup_rows(d=1):
 a=trend_rows(100)
 # Fixed known swing; the trend remains rising at the 400h completion.
 a[390]=bar(390,198,225,197,198)
 a[398]=bar(398,201,202,196,198)
 a[399]=bar(399,198,205,197,204)
 if d==-1:
  a=[dict(b,open=D(400)-b['open'],high=D(400)-b['low'],low=D(400)-b['high'],close=D(400)-b['close']) for b in a]
 return a

class IndicatorTests(unittest.TestCase):
 def test_four_hour_utc_boundary_and_sma_seed(self):
  a=trend_rows(22); z=e.trend_series(a)
  self.assertEqual(z[0]['close_time'],4*H)
  self.assertIsNone(z[18]['ema'])
  self.assertEqual(z[19]['ema'],D('109.5'))
  self.assertEqual(z[20]['ema'],D('110.5'))
 def test_incomplete_groups_excluded(self):
  a=[b for b in trend_rows(25) if b['ts']!=7*H]
  z=e.trend_series(a[1:-1]); self.assertEqual(len(z),22)
  self.assertNotIn(8*H,[x['close_time'] for x in z])
 def test_warmup_100_complete_four_hour_bars(self):
  z=e.trend_series(trend_rows(101))
  self.assertIsNone(e.trend_at(z,396*H)['direction'])
  self.assertEqual(e.trend_at(z,400*H)['direction'],1)
 def test_no_future_four_hour_close(self):
  z=e.trend_series(trend_rows(101))
  self.assertEqual(e.trend_at(z,403*H)['close_time'],400*H)
  self.assertEqual(e.trend_at(z,404*H)['close_time'],404*H)

class SignalTests(unittest.TestCase):
 def test_long_and_mirrored_short(self):
  for d in [1,-1]:
   a=setup_rows(d); s=e.signal_at(a,399)
   self.assertIsNotNone(s); self.assertEqual(s['d'],d)
   self.assertEqual(s['tp'],D(225) if d==1 else D(175))
   self.assertEqual(s['boundary'],D(202) if d==1 else D(198))
   self.assertEqual(s['sl'],D('195.9') if d==1 else D('204.1'))
 def test_strict_reclaim_and_higher_low(self):
  a=setup_rows(); a[-1]['close']=a[-2]['high']; self.assertIsNone(e.signal_at(a,399))
  a=setup_rows(); a[-1]['low']=a[-2]['low']; self.assertIsNone(e.signal_at(a,399))
 def test_no_target_preserves_raw_signal(self):
  a=setup_rows(); a[390]['high']=D(199); s=e.signal_at(a,399)
  self.assertIsNotNone(s); self.assertIsNone(s['tp'])
 def test_target_nearest_price_then_latest_center(self):
  a=setup_rows(); a[380]['high']=D(220); a[385]['high']=D(220)
  s=e.signal_at(a,399); self.assertEqual(s['tp'],D(220)); self.assertEqual(s['target_source']['center_time'],385*H)
 def test_target_72h_window_and_confirmation(self):
  a=setup_rows(); a[390]['high']=D(199); a[327]['high']=D(220); self.assertIsNone(e.signal_at(a,399)['tp'])
  a[328]['high']=D(220); a[327]['high']=D(180); self.assertEqual(e.signal_at(a,399)['tp'],D(220))
  a[328]['high']=D(185); a[398]['high']=D(220); a[399]['close']=D(221); self.assertIsNone(e.signal_at(a,399)['tp'])
 def test_missing_hour_pattern_rejected(self):
  a=setup_rows(); del a[-2]; self.assertIsNone(e.signal_at(a,len(a)-1))
 def test_future_bars_do_not_change_signal(self):
  a=setup_rows(); before=e.signal_at(a,399)
  a.extend([bar(k,204,10000,1,2000) for k in range(400,440)])
  self.assertEqual(e.signal_at(a,399),before)
 def test_unconfirmed_future_swing_excluded(self):
  a=setup_rows(); a[390]['high']=D(199); a[397]['high']=D(210)
  self.assertEqual(e.signal_at(a,399)['tp'],D(210))
  a[397]['high']=D(199); a[398]['high']=D(205); a[399]['close']=D(206); a[399]['high']=D(207)
  self.assertIsNone(e.signal_at(a,399)['tp'])

class CandidateTests(unittest.TestCase):
 def status(self,c,t,completed=(),quote=102,trend=1):
  return e.candidate_status(c,t,completed,None if quote is None else D(str(quote)),trend)
 def test_exact_expiry(self):
  c=candidate();self.assertEqual(self.status(c,403*H),'expired');self.assertEqual(self.status(c,402*H),'eligible')
 def test_completed_stop_before_delay(self):
  c=candidate();self.assertEqual(self.status(c,401*H,[bar(400,102,105,94,102)]),'cancel_sl')
 def test_completed_close_before_delay(self):
  self.assertEqual(self.status(candidate(),401*H,[bar(400,102,105,98,100)]),'cancel_close')
 def test_target_hit_before_delay(self):
  self.assertEqual(self.status(candidate(),401*H,[bar(400,102,110,101,105)]),'cancel_tp')
 def test_quote_sl_tp_and_trend_cancel(self):
  self.assertEqual(self.status(candidate(),400*H,quote=95),'cancel_sl_quote')
  self.assertEqual(self.status(candidate(),400*H,quote=110),'cancel_tp_quote')
  self.assertEqual(self.status(candidate(),400*H,trend=0),'cancel_trend')
  self.assertEqual(self.status(candidate(),400*H,quote=100),'quote_inside_boundary')
 def test_short_mirror_status(self):
  c=candidate(-1,tp=90,sl=105)
  self.assertEqual(self.status(c,400*H,quote=90,trend=-1),'cancel_tp_quote')
  self.assertEqual(self.status(c,400*H,quote=99,trend=-1),'eligible')
 def test_target_locked(self):
  c=candidate(); before=deepcopy(c); self.status(c,401*H,[bar(400,102,107,101,103)])
  self.assertEqual(c,before)

class CostExitTests(unittest.TestCase):
 def test_cost_adjusted_ratio_and_limits(self):
  c=candidate(tp=130,sl=95); p=e.plan_entry(c,D(102),400*H,D(1000))
  self.assertTrue(p['accepted']);self.assertLessEqual(p['planned_risk'],20);self.assertLessEqual(p['notional'],1000)
  self.assertEqual(p['q']%D('.0001'),0);self.assertGreaterEqual(p['planned_ratio'],1)
  self.assertFalse(e.plan_entry(candidate(tp=103),D(102),400*H,D(1000))['accepted'])
 def test_single_leg_minimum(self):
  p=e.plan_entry(candidate(tp=130,sl=95),D(102),400*H,D(2))
  self.assertEqual(p['reason'],'minimum_order')
 def test_adverse_fill_rounding(self):
  self.assertEqual(e.fill_price(D(10000),1,True),D('10003.0'))
  self.assertEqual(e.fill_price(D(10000),1,False),D('9997.0'))
  self.assertEqual(e.fill_price(D('10000.1'),-1,True),D('9997.0'))
 def test_funding_exact_boundary(self):
  self.assertEqual(e.funding_times(8*H,16*H),[16*H]); self.assertEqual(e.funding_times(7*H,8*H),[8*H])
  self.assertEqual(e.funding_times(8*H,14*H),[])
 def pos(self,d=1):
  return dict(d=d,entry_time=400*H,remaining=D(1),sl=D(95) if d==1 else D(105),tp=D(110) if d==1 else D(90))
 def test_dual_touch_sl_priority(self):
  x=e.exit_bar(self.pos(),bar(400,102,111,94,105));self.assertEqual(x[0]['reason'],'SL')
 def test_gap_stop_worse_open(self):
  x=e.exit_bar(self.pos(),bar(401,92,111,90,100)); self.assertEqual(x[0]['raw_price'],D(92));self.assertEqual(x[0]['reason'],'GAP_SL')
 def test_gap_target_fixed(self):
  x=e.exit_bar(self.pos(),bar(401,112,114,111,113)); self.assertEqual(x[0]['raw_price'],D(110));self.assertEqual(x[0]['time'],401*H)
 def test_exact_six_hour_timeout(self):
  x=e.exit_bar(self.pos(),bar(406,102,111,94,102));self.assertEqual(x[0]['reason'],'TIMEOUT'); self.assertEqual(x[0]['time'],406*H)
 def test_intrabar_exit_funding_through_open(self):
  p=self.pos(); p['entry_time']=402*H;x=e.exit_bar(p,bar(407,102,111,100,105))[0]
  self.assertEqual(x['time'],408*H-1);self.assertEqual(x['funding_through'],407*H)
 def test_exact_open_timeout_funding_included(self):
  p=self.pos(); p['entry_time']=402*H;x=e.exit_bar(p,bar(408,102,105,100,103))[0]
  self.assertEqual(e.funding_times(p['entry_time'],x['funding_through']),[408*H])

class PortfolioTests(unittest.TestCase):
 def rows(self):
  a=setup_rows();a.extend([bar(k,204,206,203,204) for k in range(400,412)]);return a
 def test_delay_preserves_invalidation(self):
  a=self.rows(); a[400]=bar(400,204,205,194,204)
  r=e.simulate(a,400*H,412*H,delay=1)
  self.assertEqual(r['candidates'][0]['outcome'],'cancel_sl');self.assertEqual(len(r['trades']),0)
 def test_known_open_no_hl_peek_and_censor(self):
  a=self.rows();a[400]=bar(400,204,230,203,225)
  full=e.simulate(a,400*H,412*H);tail=e.simulate(a[:402],400*H,402*H)
  self.assertEqual(len(full['trades']),1); self.assertEqual(full['trades'][0]['exit_path'],'TP')
  self.assertEqual(len(tail['trades']),0);self.assertEqual(len(tail['censored']),1)
  self.assertEqual(full['candidates'][0]['entry_time'],tail['candidates'][0]['entry_time'])
  self.assertEqual(full['candidates'][0]['attempts'],tail['candidates'][0]['attempts'])
 def test_account_reconciles_no_double_cost(self):
  a=self.rows();r=e.simulate(a,400*H,412*H);self.assertEqual(len(r['trades']),1)
  p=r['trades'][0];self.assertEqual(p['net'],p['raw_gross']-p['total_cost'])
  self.assertEqual(r['equity'],D(1000)+p['net']);self.assertEqual(r['equity'],r['provisional_equity'])
  direct=sum(p['d']*(x['fill']-p['entry_fill'])*x['quantity'] for x in p['exits'])-p['entry_fee']-p['exit_fee']-p['funding']-p['reserve']
  self.assertEqual(p['net'],direct)
 def test_no_target_no_candidate(self):
  a=self.rows();a[390]['high']=D(199);r=e.simulate(a,400*H,412*H)
  self.assertEqual(len(r['candidates']),0);self.assertEqual(r['raw_signals'][0]['disposition'],'no_target')
 def test_dedup_and_suppressed_active(self):
  a=self.rows();a[400]=bar(400,205,206,203,204);a[401]=bar(401,204,210,204,208)
  r=e.simulate(a,400*H,412*H);self.assertEqual(len({s['t0'] for s in r['raw_signals']}),len(r['raw_signals']))
  self.assertEqual(r['raw_signals'][1]['disposition'],'suppressed_active')

if __name__=='__main__':unittest.main()
