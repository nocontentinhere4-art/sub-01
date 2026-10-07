"""Real-account decision planner; shares the existing learner. No broker or order submission."""
import asyncio
import math
import os
import random
import time
from dataclasses import dataclass
from pathlib import Path
from aiohttp import web
from state_io import load_json, save_json
from .engine import PaperConfig, PaperEngine, adaptive_pick, identifier, number, trader_cue

KEY = web.AppKey('copytrade_account_planner', object)


@dataclass(frozen=True)
class Limits:
    budget_usd: float
    per_order_usd: float
    daily_loss_usd: float | None = None

    def __post_init__(self):
        for v in (self.budget_usd, self.per_order_usd):
            number(v, positive=True)
        if self.daily_loss_usd is not None:
            number(self.daily_loss_usd, positive=True)
        if self.per_order_usd > self.budget_usd or (self.daily_loss_usd is not None and self.daily_loss_usd > self.budget_usd):
            raise ValueError('order/loss limit exceeds budget')

    @classmethod
    def from_env(cls):
        keys=('SUB01_TRADE_BUDGET_USD','SUB01_TRADE_ORDER_USD','SUB01_TRADE_DAILY_LOSS_USD')
        if not os.environ.get(keys[0]) or not os.environ.get(keys[1]):
            return None
        return cls(float(os.environ[keys[0]]), float(os.environ[keys[1]]),
                   float(os.environ[keys[2]]) if os.environ.get(keys[2]) else None)


class AccountPlanner:
    def __init__(self, limits=None, backend=None, saved=None):
        self.limits, self.backend = limits, backend
        self.model = PaperEngine(PaperConfig())
        saved=saved or {}
        if not isinstance(saved,dict):
            raise ValueError('invalid learner state')
        for name in ('seen','receipts'):
            journal=saved.get(name,[])
            if not isinstance(journal,list) or len(journal)>10000 or any(not isinstance(v,str) for v in journal) or len(set(journal))!=len(journal):
                raise ValueError('invalid learner journal')
        for trader,values in saved.get('memory',{}).items():
            identifier(trader)
            if not isinstance(values,list) or len(values)>self.model.cfg.memory_window:
                raise ValueError('invalid learner memory')
            for value in values:number(value)
        for trader,count in saved.get('observations',{}).items():
            identifier(trader)
            if type(count) is not int or count<0:
                raise ValueError('invalid observation count')
        self.last=None
        self.seen=list(saved.get('seen',[]))[:10000]
        self.receipts=list(saved.get('receipts',[]))[:10000]
        self.model.memory=saved.get('memory',{})
        self.model.total_observations=saved.get('observations',{})
        self.rng=random.Random(self.model.cfg.seed)
        if saved.get('rng'):
            state=saved['rng'];self.rng.setstate((state[0],tuple(state[1]),state[2]))

    def public(self):
        last=None if self.last is None else {k:self.last[k] for k in ('action','asset','usd','reason')}
        return {'state':'waiting for feed' if self.limits else 'waiting for risk limits', 'last':last,
                'execution':'not connected', 'rules':{'budget_usd':self.limits.budget_usd if self.limits else None,
                'per_order_usd':self.limits.per_order_usd if self.limits else None,
                'take_profit_pct':100,'take_profit_position_pct':50,'trailing_pct':10,'stop_loss_pct':75}, 'model':'recent outcomes + uncertainty + spiking preference'}

    def saved(self):
        return {'seen':self.seen,'receipts':self.receipts,'memory':self.model.memory,
                'observations':self.model.total_observations,'rng':self.rng.getstate()}

    async def decide(self, event, account, now=None):
        elapsed_start=time.monotonic()
        now=time.time() if now is None else now
        did=identifier(event.get('id'))
        if len(self.seen)>=10000:
            raise ValueError('decision journal full')
        if did in self.seen:
            raise ValueError('duplicate decision')
        if event.get('source')!='observed' or event.get('provider')!='fomo':
            raise ValueError('observed Fomo signals required')
        t=number(event.get('t'))
        if not 0 <= now-t <= 15:
            raise ValueError('stale signal')
        signals=event.get('signals')
        if not isinstance(signals,list) or not 1 <= len(signals) <= 5:
            raise ValueError('one to five signals required')
        candidates=[];traders=set()
        for row in signals:
            trader,asset=identifier(row.get('trader')),identifier(row.get('asset'))
            qt=number(row.get('quote_t'));number(row.get('price'),positive=True)
            if row.get('side')!='buy' or trader=='cash' or trader in traders:
                raise ValueError('unique buy candidates required')
            traders.add(trader)
            if 0 <= now-qt <= 15:
                candidates.append({'trader':trader,'asset':asset})
        candidates.sort(key=lambda row:row['trader'])
        plan={'id':did,'action':'hold','asset':None,'usd':0,'reason':'waiting for risk limits'}
        if self.limits is None:
            return self.record(plan)
        if not account or account.get('mode')!='real' or account.get('provider')!='fomo' or account.get('connected') is not True:
            plan['reason']='account feed disconnected';return self.record(plan)
        updated=number(account.get('updated_at'))
        if not 0 <= now-updated <= 60:
            plan['reason']='account state stale';return self.record(plan)
        # Actual account metrics, not a paper balance; missing metrics fail closed.
        cash=number(account.get('balance_usd'))
        loss=number(account.get('daily_loss_usd'))
        exposure=number(account.get('exposure_usd'))
        opened=account.get('open_positions')
        if min(cash,loss,exposure)<0 or type(opened) is not int or opened<0:
            raise ValueError('invalid account risk metrics')
        if self.limits.daily_loss_usd is not None and loss >= self.limits.daily_loss_usd:
            plan['reason']='daily loss limit';return self.record(plan)
        if opened>=self.model.cfg.max_open:
            plan['reason']='position limit';return self.record(plan)
        usd=min(self.limits.per_order_usd,self.limits.budget_usd-exposure,cash)
        if usd<=0:
            plan['reason']='no available budget';return self.record(plan)
        if not candidates:
            plan['reason']='no fresh quotes';return self.record(plan)
        labels=[trader_cue(r['trader']) for r in candidates]+['hold cash']
        try:
            ans=await asyncio.wait_for(self.backend.ask(labels,'copytrade'),timeout=4) if self.backend else None
        except (TimeoutError, RuntimeError):
            plan['reason']='brain unavailable';return self.record(plan)
        # A slow model response must not turn an expired quote into a proposal.
        if now-t+time.monotonic()-elapsed_start>15:
            plan['reason']='signal expired during decision';return self.record(plan)
        rates=ans.get('pool_rates') if ans else None
        if not isinstance(rates,list) or len(rates)!=len(labels) or any(not isinstance(v,(int,float)) or not math.isfinite(v) for v in rates):
            rates=[0.0]*len(labels)
        mean=sum(rates)/len(rates)
        lean=[math.tanh((r-mean)/2) for r in rates]
        reps=[self.model.reputation(r['trader']) for r in candidates]
        scores=[r['score']+self.model.cfg.native_weight*lean[i] for i,r in enumerate(reps)]
        scores.append(self.model.cfg.native_weight*lean[-1])
        pick,reason=adaptive_pick(reps,scores,self.model.cfg,self.rng)
        plan['reason']=reason
        if pick<len(candidates):
            plan.update(action='buy',asset=candidates[pick]['asset'],trader=candidates[pick]['trader'],usd=usd)
        return self.record(plan)

    def record(self,plan):
        self.last=plan;self.seen=self.seen+[plan['id']]
        return plan

    def outcome(self,row):
        # A trusted connector reports settled real receipts; this module is not a chain verifier.
        if row.get('source')!='observed' or row.get('mode')!='real' or row.get('status')!='confirmed':
            raise ValueError('confirmed real outcome required')
        tx=row.get('tx');alphabet=set('123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz')
        if len(self.receipts)>=10000:
            raise ValueError('receipt journal full')
        if not isinstance(tx,str) or not 80<=len(tx)<=90 or not set(tx)<=alphabet or tx in self.receipts:
            raise ValueError('invalid or duplicate receipt')
        trader=identifier(row.get('trader'))
        cost=number(row.get('cost_usd'),positive=True);proceeds=number(row.get('proceeds_usd'))
        if proceeds<0:raise ValueError('negative proceeds')
        self.model._observe(trader,(proceeds-cost)/cost)
        self.receipts=self.receipts+[tx]


def exit_proposal(position, account, now=None):
    """Propose exits from observed holdings; only confirmed fills unlock trailing.

    The connector owns fill quantities and peak_since_tp (including across restarts).
    A proposal never changes either field, and never submits an order.
    """
    now=time.time() if now is None else now
    if not account or account.get('mode')!='real' or account.get('provider')!='fomo' or account.get('connected') is not True:
        raise ValueError('real account feed required')
    if not 0<=now-number(account.get('updated_at'))<=60:
        raise ValueError('account state stale')
    if position.get('source')!='observed' or position.get('mode')!='real':
        raise ValueError('observed real position required')
    if not 0<=now-number(position.get('quote_t'))<=15:
        raise ValueError('stale quote')
    pid=identifier(position.get('position_id'));asset=identifier(position.get('asset'))
    price=number(position.get('price'),positive=True)
    entry=number(position.get('entry_price'),positive=True)
    initial=number(position.get('initial_quantity'),positive=True)
    remaining=number(position.get('quantity'),positive=True)
    filled=number(position.get('tp_filled_quantity'))
    if remaining>initial or not 0<=filled<=initial-remaining+initial*1e-9:
        raise ValueError('inconsistent confirmed fill quantities')
    plan={'position_id':pid,'asset':asset,'action':'hold','quantity':0,'reason':'inside exit bands'}
    target=initial*0.5
    if price<=entry*0.25:
        return dict(plan,action='sell',quantity=remaining,reason='stop loss -75%')
    if filled>=target:
        peak=number(position.get('peak_since_tp'),positive=True)
        if peak<price:
            raise ValueError('peak must include current price')
        if price<=peak*0.90:
            return dict(plan,action='sell',quantity=remaining,reason='trailing stop 10%')
    elif price>=entry*2:
        return dict(plan,action='sell',quantity=min(remaining,target-filled),reason='take half at +100%')
    return plan


def attach(app,live,data_dir):
    path=Path(data_dir)/'copytrading/account-learner.json'
    planner=AccountPlanner(Limits.from_env(),getattr(live,'decider',None),load_json(path,{}))
    app[KEY]=planner
    lock=asyncio.Lock()
    async def process(request,outcome=False,exit_position=False):
        # These endpoints never inherit the X public-route exemption.
        if not os.environ.get('SITE_PASSWORD'):
            raise web.HTTPServiceUnavailable(text='private site gate required')
        if request.content_length is None or request.content_length>16384:
            raise web.HTTPRequestEntityTooLarge(max_size=16384,actual_size=request.content_length or 0)
        try:
            data=await request.json()
            if not isinstance(data,dict):raise ValueError('object required')
            async with lock:
                if outcome:
                    planner.outcome(data);result={'ok':True}
                else:
                    account=await asyncio.to_thread(load_json,Path(data_dir)/'embed/fomo.json',{})
                    result=exit_proposal(data,account) if exit_position else await planner.decide(data,account)
                await asyncio.to_thread(save_json,path,planner.saved(),allow_nan=False)
            return web.json_response(result)
        except (ValueError,TypeError,AttributeError) as e:
            raise web.HTTPBadRequest(text=str(e)) from None
    async def decide(request):return await process(request)
    async def learn(request):return await process(request,True)
    app.router.add_post('/api/copytrading/decision',decide)
    app.router.add_post('/api/copytrading/outcome',learn)
    async def exit_trade(request):return await process(request,exit_position=True)
    app.router.add_post('/api/copytrading/exit',exit_trade)
    return planner
