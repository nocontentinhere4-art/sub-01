"""Owner-configured Solana copy runner: fresh buys only, fixed $5 entries and bounded exits.

Fomo identity resolution is separate. Helius streams and confirms transactions;
Jupiter builds swaps. Nothing runs when this module is imported.
"""
import argparse
import asyncio
import base64
from collections import defaultdict
from decimal import Decimal
import fcntl
import json
import os
from pathlib import Path
import re
import time
import aiohttp
from solders.address_lookup_table_account import AddressLookupTableAccount
from solders.hash import Hash
from solders.instruction import AccountMeta,Instruction
from solders.message import MessageV0,to_bytes_versioned
from solders.pubkey import Pubkey
from solders.signature import Signature
from solders.transaction import VersionedTransaction
from .wallet import USDC,load_private,rpc_call

SOL='So11111111111111111111111111111111111111112'
TOKEN='TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA'
SYSTEM='11111111111111111111111111111111'
ATA='ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL'


def atomic(path,data,private=False):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix('.tmp')
    fd=os.open(tmp,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600 if private else 0o644)
    with os.fdopen(fd,'w') as f:json.dump(data,f,allow_nan=False);f.flush();os.fsync(f.fileno())
    os.replace(tmp,path)


def deltas(tx,owner):
    meta=tx.get('meta') or {}
    result=defaultdict(int)
    for field,sign in (('preTokenBalances',-1),('postTokenBalances',1)):
        for row in meta.get(field,[]):
            if row.get('owner')==owner:
                result[row['mint']]+=sign*int(row['uiTokenAmount']['amount'])
    return dict(result)


def detected_buy(tx,wallet,now,started):
    if not tx or (tx.get('meta') or {}).get('err') is not None:return None
    timestamp=tx.get('blockTime')
    if not isinstance(timestamp,int) or timestamp<started or not 0<=now-timestamp<=15:return None
    meta=tx['meta'];changes=deltas(tx,wallet)
    positive=[m for m,v in changes.items() if v>0 and m not in (USDC,SOL)]
    if len(positive)!=1:return None
    keys=tx['transaction']['message']['accountKeys']
    keys=[k.get('pubkey') if isinstance(k,dict) else k for k in keys]
    native_spent=0
    if wallet in keys:
        i=keys.index(wallet)
        native_spent=meta['preBalances'][i]-meta['postBalances'][i]-(meta.get('fee',0) if i==0 else 0)
    logs=' '.join(meta.get('logMessages') or []).lower()
    swap=any(word in logs for word in ('instruction: swap','instruction: buy','instruction: route','instruction: sharedaccountsroute','instruction: exactout'))
    paid=changes.get(USDC,0)<0 or changes.get(SOL,0)<0 or native_spent>100000
    return positive[0] if paid and swap else None


def exit_rule(position,quote_usdc):
    qty=int(position['quantity']);initial=int(position['initial_quantity'])
    price=Decimal(quote_usdc)/qty;entry=Decimal(position['cost_initial'])/initial
    filled=int(position.get('tp_filled',0));half=initial//2
    if price<=entry/4:return qty,'stop loss -75%'
    if filled>=half:
        peak=max(Decimal(position.get('peak',str(price))),price)
        position['peak']=str(peak)
        if price<=peak*Decimal('.9'):return qty,'trailing stop 10%'
    elif price>=entry*2:
        return min(qty,half-filled),'take half at +100%'
    return 0,'hold'


def token_bytes(account):return base64.b64decode(account['data'][0],validate=True)
def token_amount(account):return int.from_bytes(token_bytes(account)[64:72],'little')


class Runner:
    def __init__(self,args):
        self.cfg,self.key,self.rpc=load_private(args.private_config)
        if self.cfg.get('budget_usd')!=100 or self.cfg.get('per_trade_usd')!=5:
            raise ValueError('configured limits differ from authorized $100/$5')
        self.execute=args.execute
        if self.execute and self.cfg.get('enabled') is not True:raise ValueError('private execution switch is off')
        self.wallet=str(self.key.pubkey());self.data=Path(args.data_dir)
        self.path=Path(args.private_config).parent/'copy-runner-state.json'
        self.lockfile=open(self.path.with_suffix('.lock'),'a');os.chmod(self.lockfile.name,0o600)
        fcntl.flock(self.lockfile,fcntl.LOCK_EX|fcntl.LOCK_NB)
        self.state=json.loads(self.path.read_text()) if self.path.exists() else {'version':1,'positions':{},'seen':[],'operations':[],'pending':None,'realized_loss_usd':0}
        if self.state.get('version')!=1 or not isinstance(self.state.get('positions'),dict):raise ValueError('invalid execution state')
        self.watch={r['wallet']:r['handle'] for r in json.loads(Path(args.watchlist).read_text())['traders']}
        for address in self.watch:Pubkey.from_string(address)
        if not self.watch or self.wallet in self.watch:raise ValueError('invalid watchlist')
        self.started=int(time.time());self.queue=asyncio.Queue(maxsize=100)
        self.last_jupiter=0;self.jupiter_lock=asyncio.Lock();self.order_lock=asyncio.Lock()
        self.connected=False;self.halted=bool(self.state.get('pending'));self.last_error=None
        self.save()

    def save(self):atomic(self.path,self.state,True)
    def log(self,message):print(time.strftime('%H:%M:%S')+' '+message,flush=True)

    async def jupiter(self,endpoint,params):
        async with self.jupiter_lock:
            await asyncio.sleep(max(0,2.1-(time.monotonic()-self.last_jupiter)))
            self.last_jupiter=time.monotonic()
            headers={'x-api-key':self.cfg['jupiter_api_key']} if self.cfg.get('jupiter_api_key') else {}
            try:
                async with self.session.get('https://api.jup.ag/swap/v2/'+endpoint,params=params,headers=headers,allow_redirects=False) as r:
                    if r.status!=200:raise ValueError('Jupiter HTTP '+str(r.status))
                    q=await r.json()
            except (aiohttp.ClientError,TimeoutError):raise ValueError('Jupiter unavailable') from None
        if not isinstance(q,dict) or q.get('errorCode') or q.get('error') or int(q.get('outAmount',0))<=0:raise ValueError('no usable swap route')
        return q

    async def holdings(self):
        result=await rpc_call(self.session,self.rpc,'getTokenAccountsByOwner',[self.wallet,{'programId':TOKEN},{'encoding':'base64','commitment':'confirmed'}])
        balance=await rpc_call(self.session,self.rpc,'getBalance',[self.wallet,{'commitment':'confirmed'}])
        return result['value'],balance['value']

    async def transaction(self,signature):
        for delay in (0,.4,1,2):
            if delay:await asyncio.sleep(delay)
            tx=await rpc_call(self.session,self.rpc,'getTransaction',[signature,{'encoding':'jsonParsed','commitment':'confirmed','maxSupportedTransactionVersion':1}])
            if tx:return tx
        return None

    async def build(self,mint,amount,buy):
        params={'inputMint':USDC if buy else mint,'outputMint':mint if buy else USDC,'amount':str(amount),'taker':self.wallet,'slippageBps':'100'}
        q=await self.jupiter('build',params)
        if q.get('inputMint')!=params['inputMint'] or q.get('outputMint')!=params['outputMint'] or int(q.get('inAmount',0))!=amount or q.get('swapMode')!='ExactIn' or not 0<=int(q.get('slippageBps',10001))<=100:
            raise ValueError('swap intent mismatch')
        minimum=int(q.get('otherAmountThreshold',0))
        if minimum<=0 or Decimal(minimum)<Decimal(q['outAmount'])*Decimal('.99'):raise ValueError('invalid minimum output')
        if q.get('tipInstruction'):raise ValueError('unexpected optional tip')
        rows=q.get('computeBudgetInstructions',[])+q.get('setupInstructions',[])+[q['swapInstruction']]
        if q.get('cleanupInstruction'):rows.append(q['cleanupInstruction'])
        rows+=q.get('otherInstructions',[])
        instructions=[Instruction(Pubkey.from_string(r['programId']),base64.b64decode(r['data'],validate=True),[AccountMeta(Pubkey.from_string(a['pubkey']),a['isSigner'],a['isWritable']) for a in r['accounts']]) for r in rows]
        alts=[AddressLookupTableAccount(Pubkey.from_string(k),[Pubkey.from_string(a) for a in values]) for k,values in (q.get('addressesByLookupTableAddress') or {}).items()]
        meta=q['blockhashWithMetadata'];blockhash=Hash.from_bytes(bytes(meta['blockhash']))
        message=MessageV0.try_compile(self.key.pubkey(),instructions,alts,blockhash)
        if message.header.num_required_signatures!=1 or message.account_keys[0]!=self.key.pubkey():raise ValueError('unexpected transaction signer')
        return q,VersionedTransaction.populate(message,[Signature.default()]),minimum

    async def simulate(self,tx,mint,amount,buy,minimum):
        mint_account=await rpc_call(self.session,self.rpc,'getAccountInfo',[mint,{'encoding':'base64','commitment':'confirmed'}])
        info=mint_account['value']
        if not info or info['owner']!=TOKEN or len(token_bytes(info))!=82 or int.from_bytes(token_bytes(info)[46:50],'little')!=0:
            raise ValueError('token uses unsupported program or freeze authority')
        decimals=token_bytes(info)[44]
        before,sol=await self.holdings()
        destination=str(Pubkey.find_program_address([bytes(self.key.pubkey()),bytes(Pubkey.from_string(TOKEN)),bytes(Pubkey.from_string(mint))],Pubkey.from_string(ATA))[0])
        addresses=[self.wallet]+[r['pubkey'] for r in before]
        if destination not in addresses:addresses.append(destination)
        if len(addresses)>50:raise ValueError('too many wallet accounts')
        previous={r['pubkey']:r['account'] for r in before}
        simulation=await rpc_call(self.session,self.rpc,'simulateTransaction',[base64.b64encode(bytes(tx)).decode(),{'encoding':'base64','sigVerify':False,'replaceRecentBlockhash':True,'commitment':'confirmed','accounts':{'encoding':'base64','addresses':addresses}}])
        value=simulation['value'];after=value.get('accounts')
        if value['err'] is not None or not isinstance(after,list) or len(after)!=len(addresses):raise ValueError('swap simulation failed')
        root=after[0]
        if not root or root['owner']!=SYSTEM or root['data'][0] or sol-root['lamports']>3000000 or root['lamports']<1000000:
            raise ValueError('gas or wallet balance guard')
        changes=defaultdict(int)
        for address,new in zip(addresses[1:],after[1:]):
            old=previous.get(address)
            if not new:raise ValueError('token account unexpectedly closed')
            raw=token_bytes(new)
            if new['owner']!=TOKEN or str(Pubkey.from_bytes(raw[32:64]))!=self.wallet:raise ValueError('unexpected token owner')
            if old:
                prior=token_bytes(old)
                if old['owner']!=new['owner'] or prior[:64]+prior[72:]!=raw[:64]+raw[72:]:raise ValueError('token authority changed')
                old_amount=token_amount(old)
            else:
                if raw[72:76]!=bytes(4) or raw[129:133]!=bytes(4):raise ValueError('unexpected token delegate')
                old_amount=0
            changes[str(Pubkey.from_bytes(raw[:32]))]+=token_amount(new)-old_amount
        wanted_input=USDC if buy else mint;wanted_output=mint if buy else USDC
        if changes[wanted_input]!=-amount or changes[wanted_output]<minimum or any(v<0 for m,v in changes.items() if m!=wanted_input):
            raise ValueError('simulation asset deltas mismatch')
        return decimals

    async def submit(self,mint,amount,buy,reason,trader=None,source=None,source_time=None):
        if self.halted:raise ValueError('unreconciled pending transaction')
        if not self.execute:
            self.log('DRY RUN '+('buy ' if buy else 'sell ')+mint);return
        q,tx,minimum=await self.build(mint,amount,buy)
        decimals=await self.simulate(tx,mint,amount,buy,minimum)
        if source_time is not None and time.time()-source_time>15:raise ValueError('source buy expired before signing')
        signature=self.key.sign_message(to_bytes_versioned(tx.message))
        signed=VersionedTransaction.populate(tx.message,[signature])
        pending={'signature':str(signature),'mint':mint,'amount':amount,'buy':buy,'reason':reason,'trader':trader,'source':source,'decimals':decimals,'submitted_at':time.time()}
        self.state['pending']=pending;self.halted=True;self.save()
        returned=await rpc_call(self.session,self.rpc,'sendTransaction',[base64.b64encode(bytes(signed)).decode(),{'encoding':'base64','skipPreflight':False,'preflightCommitment':'confirmed','maxRetries':2}])
        if returned!=str(signature):raise ValueError('unexpected transaction signature')
        for _ in range(15):
            if await self.reconcile():return
            await asyncio.sleep(2)
        raise ValueError('confirmation pending')

    async def reconcile(self):
        pending=self.state.get('pending')
        if not pending:self.halted=False;return True
        status=await rpc_call(self.session,self.rpc,'getSignatureStatuses',[[pending['signature']],{'searchTransactionHistory':True}])
        row=status['value'][0]
        if not row:return False
        if row.get('err') is not None:
            self.state['pending']=None;self.halted=False;self.save();self.log('Transaction failed on chain');return True
        if row.get('confirmationStatus') not in ('confirmed','finalized'):return False
        tx=await self.transaction(pending['signature'])
        if not tx:return False
        changes=deltas(tx,self.wallet);mint=pending['mint'];amount=changes.get(mint,0);cash=changes.get(USDC,0)
        positions=self.state['positions']
        if pending['buy']:
            if amount<=0 or cash!=-5000000:raise ValueError('confirmed entry cannot be reconciled')
            positions[mint]={'initial_quantity':amount,'quantity':amount,'cost_initial':-cash,'cost_remaining':-cash,'tp_filled':0,'trader':pending['trader'],'decimals':pending['decimals']}
        else:
            pos=positions[mint];sold=-amount
            if sold<=0 or sold>pos['quantity'] or cash<=0:raise ValueError('confirmed exit cannot be reconciled')
            cost=pos['cost_remaining']*sold//pos['quantity']
            pos['cost_remaining']-=cost;pos['quantity']-=sold
            self.state['realized_loss_usd']+=max(0,cost-cash)/1000000
            if pending['reason']=='take half at +100%':pos['tp_filled']+=sold
            if not pos['quantity']:del positions[mint]
        self.state['operations'].append({'side':'buy' if pending['buy'] else 'sell','asset':mint[:8],'amount':abs(amount)/10**pending['decimals'],'status':'confirmed','tx':pending['signature'],'mint':mint})
        self.state['operations']=self.state['operations'][-100:]
        self.state['pending']=None;self.halted=False;self.save()
        self.log(('BUY' if pending['buy'] else 'SELL')+' CONFIRMED '+pending['signature'])
        return True

    async def consume(self):
        while True:
            signature,wallet=await self.queue.get()
            try:
                if signature in self.state['seen']:continue
                if len(self.state['seen'])>=100000:raise ValueError('signal journal full')
                self.state['seen'].append(signature);self.save()
                tx=await self.transaction(signature)
                mint=detected_buy(tx,wallet,time.time(),self.started)
                if not mint:continue
                atomic(self.data/'copytrading/display-intent.json',{'mint':mint,'revision':signature,'updated_at':time.time()})
                async with self.order_lock:
                    if self.halted or mint in self.state['positions'] or len(self.state['positions'])>=4:continue
                    cost=sum(p['cost_remaining'] for p in self.state['positions'].values())
                    accounts,_=await self.holdings()
                    cash=sum(token_amount(r['account']) for r in accounts if str(Pubkey.from_bytes(token_bytes(r['account'])[:32]))==USDC)
                    owned=sum(token_amount(r['account']) for r in accounts if str(Pubkey.from_bytes(token_bytes(r['account'])[:32]))==mint)
                    if owned or cash<5000000 or cost+5000000>100000000:continue
                    if time.time()-tx['blockTime']>15:continue
                    self.log('Fresh buy from '+self.watch[wallet]+' '+mint)
                    await self.submit(mint,5000000,True,'copy followed buy',self.watch[wallet],signature,tx['blockTime'])
            except Exception as e:
                self.last_error=str(e) if isinstance(e,ValueError) else type(e).__name__
                self.log('Entry held: '+self.last_error)
            finally:self.queue.task_done()

    async def exits(self):
        while True:
            try:
                async with self.order_lock:
                    if self.halted:await self.reconcile()
                    if not self.halted:
                        for mint in list(self.state['positions']):
                            pos=self.state['positions'].get(mint)
                            if not pos:continue
                            q=await self.jupiter('order',{'inputMint':mint,'outputMint':USDC,'amount':str(pos['quantity']),'slippageBps':'100'})
                            if q.get('inputMint')!=mint or q.get('outputMint')!=USDC or int(q.get('inAmount',0))!=pos['quantity']:raise ValueError('exit price quote mismatch')
                            amount,reason=exit_rule(pos,int(q['outAmount']));self.save()
                            if amount:await self.submit(mint,amount,False,reason)
            except Exception as e:
                self.last_error=str(e) if isinstance(e,ValueError) else type(e).__name__;self.log('Exit check: '+self.last_error)
            await asyncio.sleep(3)

    async def stream(self):
        wsurl=self.rpc.replace('https://','wss://',1)
        while True:
            try:
                async with self.session.ws_connect(wsurl,heartbeat=20,receive_timeout=90,max_msg_size=1048576) as ws:
                    requests={i:wallet for i,wallet in enumerate(self.watch,1)};subscriptions={}
                    for i,wallet in requests.items():
                        await ws.send_json({'jsonrpc':'2.0','id':i,'method':'logsSubscribe','params':[{'mentions':[wallet]},{'commitment':'confirmed'}]})
                    async for message in ws:
                        if message.type!=aiohttp.WSMsgType.TEXT:break
                        data=json.loads(message.data)
                        if 'id' in data:
                            if data.get('error'):raise ValueError('Helius subscription rejected')
                            subscriptions[data['result']]=requests[data['id']]
                            if len(subscriptions)==len(self.watch):self.connected=True;self.log('LIVE: '+str(len(self.watch))+' followed wallets subscribed')
                        elif data.get('method')=='logsNotification':
                            payload=data['params'];row=payload['result']['value'];wallet=subscriptions.get(payload['subscription'])
                            if wallet and row.get('err') is None:
                                try:self.queue.put_nowait((row['signature'],wallet))
                                except asyncio.QueueFull:self.log('Signal queue full; skipped stale-risk signal')
            except Exception as e:self.log('Stream reconnect: '+(str(e) if isinstance(e,ValueError) else type(e).__name__))
            finally:self.connected=False
            await asyncio.sleep(3)

    async def heartbeat(self):
        while True:
            try:
                accounts,sol=await self.holdings()
                cash=sum(token_amount(r['account']) for r in accounts if str(Pubkey.from_bytes(token_bytes(r['account'])[:32]))==USDC)/1000000
                out={'version':1,'provider':'fomo','mode':'real','connected':self.connected and not self.halted,'updated_at':time.time(),'executions':self.state['operations'][-8:],'balance_usd':cash,'daily_loss_usd':self.state['realized_loss_usd'],'exposure_usd':sum(p['cost_remaining'] for p in self.state['positions'].values())/1000000,'open_positions':len(self.state['positions'])}
                atomic(self.data/'embed/fomo.json',out)
                atomic(self.data/'copytrading/runner-status.json',{'running':True,'execution_enabled':self.execute,'connected':self.connected,'halted':self.halted,'following':list(self.watch.values()),'positions':len(self.state['positions']),'balance_usd':cash,'sol_gas':sol/1000000000,'last_error':self.last_error,'updated_at':time.time()})
            except Exception as e:self.log('Heartbeat: '+type(e).__name__)
            await asyncio.sleep(10)

    async def run(self):
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=25)) as session:
            self.session=session
            if self.halted:await self.reconcile()
            await asyncio.gather(self.stream(),self.consume(),self.exits(),self.heartbeat())


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--private-config',required=True);parser.add_argument('--watchlist',required=True);parser.add_argument('--data-dir',required=True);parser.add_argument('--execute',action='store_true')
    args=parser.parse_args()
    try:asyncio.run(Runner(args).run())
    except KeyboardInterrupt:pass
    except Exception as e:
        print('Runner stopped: '+(str(e) if isinstance(e,ValueError) else type(e).__name__),flush=True)
        raise SystemExit(1)

if __name__=='__main__':main()
