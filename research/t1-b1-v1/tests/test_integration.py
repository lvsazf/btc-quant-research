import unittest,sys,datetime,hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from rules import daily_states,validate_bars,simulate,VERSION,MANIFEST,H
from run_research import native_signals,check_fresh,load_history

def bars(days=60):return [dict(ts=i*H,open=100+i//24,close=100+i//24,high=100+i//24,low=100+i//24,volume=1) for i in range(days*24)]
class Integration(unittest.TestCase):
 def test_frozen_hashes(self):
  for r in MANIFEST['frozen_references']:self.assertEqual(hashlib.sha256((ROOT/r['path']).read_bytes()).hexdigest(),r['sha256'])
 def test_native_t1(self):
  df,s=native_signals(bars(),'T1');self.assertTrue(df.iloc[-1].enter_long);self.assertFalse(s.confirm_trade_entry());self.assertEqual(s.leverage(),1)
 def test_native_b1(self):
  df,s=native_signals(bars(),'B1');self.assertTrue(df.iloc[-1].enter_long)
 def test_live_mode_rejected(self):
  df,s=native_signals(bars(),'T1');s.config['runmode']='live'
  with self.assertRaises(RuntimeError):s.bot_start()
 def test_dryrun_mode_rejected(self):
  df,s=native_signals(bars(),'B1');s.config['runmode']='dry_run'
  with self.assertRaises(RuntimeError):s.populate_entry_trend(df,{'pair':'BTC/USDT:USDT'})
 def test_marker_required(self):
  df,s=native_signals(bars(),'T1');s.config['t1b1_research_only']=False
  with self.assertRaises(RuntimeError):s.bot_start()
 def test_gap_rejected(self):
  b=bars();del b[2]
  with self.assertRaises(ValueError):validate_bars(b)
 def test_prefix_invariance(self):
  a,_=native_signals(bars(55),'T1');b,_=native_signals(bars(60),'T1')
  self.assertEqual(a.enter_long.tolist(),b.enter_long.iloc[:len(a)].tolist())
 def test_stale_rejected(self):
  now=int(datetime.datetime.now(datetime.timezone.utc).timestamp()*1000)
  with self.assertRaises(ValueError):check_fresh({'data':{'serverTime':now-61000}},{'data':[{'ts':now}]})
 def test_future_rejected(self):
  now=int(datetime.datetime.now(datetime.timezone.utc).timestamp()*1000)
  with self.assertRaises(ValueError):check_fresh({'data':{'serverTime':now+5000}},{'data':[{'ts':now}]})
 def test_original_actual_results(self):
  base=Path('/workspace/shared/btc-quant-research-20261010');bs=load_history(base);states,_=daily_states(bs)
  from rules import load_csv
  rates={r['ts']:r['fundingRate'] for r in load_csv(base/'data/btcusdt_usdt_futures_funding.csv')};marks={r['ts']:r for r in load_csv(base/'data/btcusdt_usdt_futures_mark_1h_funding_window.csv')}
  cut=[b for b in bs if min(rates)<=b['ts']<=max(rates)]
  for name,expected in [('HOLD',254.86655421240835),('T1',189.19495756895435),('B1',74.38798335933006)]:
   r,*_=simulate(cut,name,states,rates,marks);self.assertAlmostEqual(r['pnl'],expected,places=7)
if __name__=='__main__':unittest.main()
