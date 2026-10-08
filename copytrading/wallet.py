"""Private Solana configuration and read-only Helius checks. No transaction submission."""
import json
import os
import stat
from pathlib import Path
from urllib.parse import urlsplit, parse_qs, urlencode
import aiohttp

USDC='EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v'


def helius_url(value):
    if not isinstance(value,str) or not value.strip():
        raise ValueError('Helius credential missing')
    value=value.strip()
    if '://' not in value:
        if not value.isascii() or not all(c.isalnum() or c in '-_' for c in value):
            raise ValueError('invalid Helius key format')
        return 'https://mainnet.helius-rpc.com/?'+urlencode({'api-key':value})
    try:
        u=urlsplit(value);port=u.port
    except ValueError:
        raise ValueError('invalid Helius endpoint') from None
    if u.scheme!='https' or u.hostname!='mainnet.helius-rpc.com' or u.username or u.password or port not in (None,443) or u.path not in ('','/') or u.fragment:
        raise ValueError('Helius mainnet HTTPS endpoint required')
    q=parse_qs(u.query)
    if set(q)!={'api-key'} or len(q['api-key'])!=1 or not q['api-key'][0]:
        raise ValueError('Helius API key missing')
    return value


def load_private(path):
    from solders.keypair import Keypair
    from solders.pubkey import Pubkey
    path=Path(path)
    fd=os.open(path,os.O_RDONLY | getattr(os,'O_NOFOLLOW',0))
    with os.fdopen(fd) as f:
        st=os.fstat(f.fileno())
        if not stat.S_ISREG(st.st_mode) or stat.S_IMODE(st.st_mode)&0o077 or st.st_uid!=os.getuid() or st.st_size>16384:
            raise ValueError('private wallet file requires owner-only permissions')
        try:cfg=json.load(f)
        except (ValueError,UnicodeError):raise ValueError('invalid private configuration JSON') from None
    if not isinstance(cfg,dict):raise ValueError('private configuration must be an object')
    key=cfg.get('private_key') or cfg.get('seed_phrase')
    try:
        if isinstance(key,str) and key.strip().startswith('['):key=json.loads(key)
        if isinstance(key,list):
            if len(key)!=64 or any(type(v) is not int or not 0<=v<=255 for v in key):raise ValueError()
            signer=Keypair.from_bytes(bytes(key))
        elif isinstance(key,str) and len(key.strip().split())==1:
            signer=Keypair.from_base58_string(key.strip())
        else:raise ValueError()
        expected=Pubkey.from_string(cfg.get('expected_fomo_wallet_address','').strip())
    except Exception:
        raise ValueError('invalid private key or expected public wallet format') from None
    if signer.pubkey()!=expected:
        raise ValueError('private key does not match expected Fomo wallet')
    rpc=helius_url(cfg.get('helius_rpc_url') or cfg.get('helius_api_key'))
    return cfg,signer,rpc


async def rpc_call(session,url,method,params):
    try:
        async with session.post(url,json={'jsonrpc':'2.0','id':1,'method':method,'params':params},allow_redirects=False) as r:
            if r.status!=200:raise ValueError('Helius request rejected')
            data=await r.json()
    except (aiohttp.ClientError,TimeoutError):
        raise ValueError('Helius connection failed') from None
    if isinstance(data,dict) and data.get('error'):
        code=data['error'].get('code') if isinstance(data['error'],dict) else None
        raise ValueError('Helius RPC failed'+(' (code '+str(code)+')' if type(code) is int else ''))
    if not isinstance(data,dict) or 'result' not in data:
        raise ValueError('Helius RPC failed')
    return data['result']


async def inspect_wallet(path):
    _,signer,rpc=load_private(path)
    public=str(signer.pubkey())
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:
        sol=await rpc_call(session,rpc,'getBalance',[public,{'commitment':'confirmed'}])
        tokens=await rpc_call(session,rpc,'getTokenAccountsByOwner',[public,{'mint':USDC},{'encoding':'jsonParsed','commitment':'confirmed'}])
    usdc=sum(int(r['account']['data']['parsed']['info']['tokenAmount']['amount']) for r in tokens['value'])/1_000_000
    return {'wallet_matches_fomo':True,'helius_connected':True,'sol_balance':sol['value']/1_000_000_000,'usdc_balance':usdc}
