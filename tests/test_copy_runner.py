from decimal import Decimal
import sys,time
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
pytest.importorskip('solders')
from copytrading.runner import exit_rule,detected_buy,USDC,SOL
from copytrading.wallet import helius_url,load_private


def pos():return {'initial_quantity':1000,'quantity':1000,'cost_initial':5000000,'tp_filled':0}


def test_exit_rules_and_partial_fills():
 p=pos()
 assert exit_rule(p,9999999)[0]==0
 assert exit_rule(p,10000000)==(500,'take half at +100%')
 assert p['tp_filled']==0
 p.update(quantity=750,tp_filled=250)
 assert exit_rule(p,7500000)[0]==250
 p.update(quantity=500,tp_filled=500)
 assert exit_rule(p,6000000)[0]==0
 assert p['peak']==str(Decimal(12000))
 assert exit_rule(p,5400000)==(500,'trailing stop 10%')
 assert exit_rule(pos(),1250000)==(1000,'stop loss -75%')
 assert exit_rule(pos(),1250001)[0]==0


def tx():
 return {'blockTime':1000,'transaction':{'message':{'accountKeys':['wallet']}},'meta':{'err':None,'fee':5000,'preBalances':[10000000],'postBalances':[9995000],'logMessages':['Program log: Instruction: Swap'],'preTokenBalances':[{'owner':'wallet','mint':USDC,'uiTokenAmount':{'amount':'5000000'}}],'postTokenBalances':[{'owner':'wallet','mint':'coin','uiTokenAmount':{'amount':'100'}},{'owner':'wallet','mint':USDC,'uiTokenAmount':{'amount':'0'}}]}}


def test_only_fresh_actual_swaps_trigger_entries():
 assert detected_buy(tx(),'wallet',1001,999)=='coin'
 assert detected_buy(tx(),'wallet',1016,999) is None
 assert detected_buy(tx(),'wallet',1001,1001) is None
 t=tx();t['meta']['logMessages']=[]
 assert detected_buy(t,'wallet',1001,999) is None
 t=tx();t['meta']['err']={'InstructionError':[0,'x']}
 assert detected_buy(t,'wallet',1001,999) is None
 assert detected_buy(tx(),'different_wallet',1001,999) is None
 t=tx();t['meta']['postTokenBalances'].append({'owner':'wallet','mint':'second','uiTokenAmount':{'amount':'100'}})
 assert detected_buy(t,'wallet',1001,999) is None


def test_helius_never_accepts_unrelated_hosts_or_echoes_bad_credentials():
 assert helius_url('test_key').startswith('https://mainnet.helius-rpc.com/')
 for v in ('https://evil.example/?api-key=secret','https://mainnet.helius-rpc.com:secret/?api-key=x'):
  with pytest.raises(ValueError) as e:helius_url(v)
  assert 'secret' not in str(e.value)


def test_private_key_matching_and_permissions(tmp_path):
 import json,os
 from solders.keypair import Keypair
 k=Keypair();p=tmp_path/'private.json'
 d={'private_key':str(k),'expected_fomo_wallet_address':str(k.pubkey()),'helius_rpc_url':'dummy'}
 p.write_text(json.dumps(d));os.chmod(p,0o600)
 assert load_private(p)[1].pubkey()==k.pubkey()
 d['expected_fomo_wallet_address']=str(Keypair().pubkey());p.write_text(json.dumps(d))
 with pytest.raises(ValueError,match='does not match'):load_private(p)
 os.chmod(p,0o644)
 with pytest.raises(ValueError,match='owner-only'):load_private(p)
