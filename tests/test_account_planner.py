import asyncio
import sys
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from copytrading.account import AccountPlanner, Limits, exit_proposal, attach
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer
from types import SimpleNamespace
from live_server import password_gate


def account(**kw):
    return dict(mode='real',provider='fomo',connected=True,updated_at=1000,balance_usd=100,
                exposure_usd=0,daily_loss_usd=0,open_positions=0,**kw)


def signal(i='one', **kw):
    return dict(id=i,source='observed',provider='fomo',t=1000,
                signals=[dict(trader='alice',asset='SOL',side='buy',quote_t=1000,price=1)],**kw)


def position(**kw):
    p=dict(position_id='position1',asset='SOL',source='observed',mode='real',quote_t=1000,
           price=1,entry_price=1,initial_quantity=5,quantity=5,tp_filled_quantity=0)
    p.update(kw);return p


def decide(planner,event=None,acct=None):
    return asyncio.run(planner.decide(event or signal(),account() if acct is None else acct,now=1000))


def test_entry_uses_actual_budget_and_journal_survives_restart():
    p=AccountPlanner(Limits(100,5))
    assert decide(p)['usd']==5
    restored=AccountPlanner(Limits(100,5),saved=p.saved())
    with pytest.raises(ValueError,match='duplicate'):decide(restored)
    a=account();a['exposure_usd']=98
    assert decide(restored,signal('two'),a)['usd']==2


@pytest.mark.parametrize('field,value,reason',[
    ('balance_usd',0,'no available budget'),('exposure_usd',100,'no available budget'),
    ('connected',False,'disconnected'),('updated_at',900,'stale'),
    ('mode','paper','disconnected'),('open_positions',4,'position limit'),
    ('daily_loss_usd',20,'daily loss limit')])
def test_real_account_risk_guards(field,value,reason):
    a=account();a[field]=value
    r=decide(AccountPlanner(Limits(100,5,20)),acct=a)
    assert r['action']=='hold' and reason in r['reason']


def test_missing_limits_quotes_and_metrics_fail_closed():
    assert decide(AccountPlanner())['action']=='hold'
    s=signal();s['signals'][0]['quote_t']=980
    assert decide(AccountPlanner(Limits(100,5)),s)['reason']=='no fresh quotes'
    a=account();del a['balance_usd']
    with pytest.raises(ValueError):decide(AccountPlanner(Limits(100,5)),acct=a)


def test_real_outcomes_change_preferences_and_cannot_replay():
    p=AccountPlanner(Limits(100,5))
    for n in range(2):
        p.outcome(dict(source='observed',mode='real',status='confirmed',tx=str(n+2)*88,
                       trader='alice',cost_usd=5,proceeds_usd=1))
    p.model.cfg=__import__('dataclasses').replace(p.model.cfg,exploration=0)
    assert decide(p)['action']=='hold'
    restored=AccountPlanner(saved=p.saved())
    with pytest.raises(ValueError,match='duplicate'):
        restored.outcome(dict(source='observed',mode='real',status='confirmed',tx='2'*88,
                             trader='alice',cost_usd=5,proceeds_usd=10))
    with pytest.raises(ValueError,match='confirmed'):
        restored.outcome(dict(source='observed',mode='paper',status='confirmed'))


@pytest.mark.parametrize('price,action,qty',[(1.99,'hold',0),(2,'sell',2.5),(.251,'hold',0),(.25,'sell',5),(.1,'sell',5)])
def test_exit_thresholds(price,action,qty):
    result=exit_proposal(position(price=price),account(),now=1000)
    assert (result['action'],result['quantity'])==(action,qty)


def test_trailing_requires_confirmed_half_fill_and_persistent_peak():
    unfilled=position(price=1.8)
    assert exit_proposal(unfilled,account(),now=1000)['action']=='hold'
    partial=position(price=2,quantity=4,tp_filled_quantity=1)
    assert exit_proposal(partial,account(),now=1000)['quantity']==1.5
    filled=position(price=2.7,quantity=2.5,tp_filled_quantity=2.5,peak_since_tp=3)
    assert exit_proposal(filled,account(),now=1000)['quantity']==2.5
    filled['price']=2.71
    assert exit_proposal(filled,account(),now=1000)['action']=='hold'
    filled.pop('peak_since_tp')
    with pytest.raises(ValueError):exit_proposal(filled,account(),now=1000)
    with pytest.raises(ValueError,match='stale'):
        exit_proposal(position(quote_t=980),account(),now=1000)


def test_private_trading_endpoints_never_open_through_player(monkeypatch,tmp_path):
    monkeypatch.setenv('SITE_PASSWORD','private')
    async def check():
        app=web.Application(middlewares=[password_gate('private')])
        attach(app,SimpleNamespace(decider=None),tmp_path)
        async with TestClient(TestServer(app)) as client:
            for route in ('decision','outcome','exit'):
                r=await client.post('/api/copytrading/'+route,json={})
                assert r.status==401
    asyncio.run(check())
