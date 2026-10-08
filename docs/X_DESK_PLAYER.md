# SUB-01 desk player for X

The player shows the existing character at the desk with the logo's orange (#ff6a00) on SUB-01 labels, accents, links and monitor placeholder. The official Fomo page retains its own appearance. No viewer can place an order through the player.

## Public player

Set `SUB01_X_EMBED=1` and `SUB01_PUBLIC_URL=https://your-public-origin`. `/share/sub01` declares an X Player Card with a 480 × 480 iframe at `/embed/sub01` and a static PNG fallback. Public HTTPS and an actual X card test are still required; local rendering does not prove acceptance by X.

The existing password gate remains on `/`, `/ws`, private APIs and original room assets. Only exact GET/HEAD player routes and selected assets are public. This switch is off by default. Rendering is capped at 30 fps, pauses when hidden, and never starts another brain.

## Dedicated account and reviewed screen

The owner logged into the dedicated account SUBZERONE01 in Chrome and authorized showing nickname, balance, charts, token buys/sells, amounts and transaction links. Cookies, credentials and security dialogs remain private. Browser login is not server-side account integration.

`/embed/fomo-frame.jpg` exposes only the exact reviewed JPEG at `data_dir/embed/fomo-reviewed-frame.jpg` when its SHA-256 matches `SUB01_FOMO_FRAME_SHA256`. The file is bounded to 4 MiB and 1080p and verified as JPEG. Changed files fail closed. It is labelled a captured preview. Account frames and cookie files are never committed. A continuous live browser bridge remains pending.

A trusted server-side connector may write `data_dir/embed/fomo.json`: `version:1`, `provider:"fomo"`, `mode:"real"`, `connected:true`, `updated_at` (Unix seconds) and `executions`. Confirmed execution rows contain `side`, public `asset`, positive token `amount` and Solana `tx` signature. The public reader redacts extra fields, limits eight rows, rejects paper/pending/malformed records and marks heartbeats older than 60 seconds disconnected. Confirmation is reported by the connector, not verified on chain by this module.

## Decision logic and owner's exit rules

The account planner reuses the existing copy-trading controller's recent-outcome memory, uncertainty penalty, cold-start exploration and spiking preference. It proposes entries from observed Fomo signals and learns trader reputation from confirmed real outcomes. It does not use simulated fills or a paper balance for these decisions. It reuses the live brain backend; this change does not increase neuron count or start GPU resources. Real outcome attribution to native synaptic learning is not added here.

The owner selected **$100 budget, $5 per entry, sell half of the original token quantity at +100%, then a 10% trailing stop on the remainder, initial stop at -75%**. Taking half means half the position, not withdrawing half of dollar profit. Trailing activates after confirmed fills reach half the original quantity; partial take-profit fills leave only the outstanding target quantity to sell. Exit proposals never count as fills.

Configure `SUB01_TRADE_BUDGET_USD=100` and `SUB01_TRADE_ORDER_USD=5` on the server. Without these, entries hold. Optional `SUB01_TRADE_DAILY_LOSS_USD` is a separate daily limit; the owner has not specified one. The -75% stop is per-position, not a daily loss cap. Four open positions are allowed by the shared controller. Entries are clipped to actual cash and remaining exposure budget. Missing actual risk metrics, stale signals/quotes, stale or disconnected account state, exhausted budgets or a specified daily loss cap prevent entry proposals.

Private, password-gated connector endpoints:

- `POST /api/copytrading/decision`: `id`, `source:"observed"`, `provider:"fomo"`, `t`, and 1–5 unique buy `signals` with `trader`, `asset`, `side`, `quote_t`, positive `price`. Signals and quotes expire after 15 seconds. The trusted account snapshot additionally supplies actual `balance_usd`, `daily_loss_usd` (nonnegative loss measure), `exposure_usd`, and integer `open_positions`.
- `POST /api/copytrading/outcome`: `source:"observed"`, `mode:"real"`, `status:"confirmed"`, unique settled `tx`, `trader`, positive `cost_usd`, nonnegative `proceeds_usd`. The connector must verify ownership/settlement and report matched trade outcomes rather than partial unrelated proceeds.
- `POST /api/copytrading/exit`: observed real `position_id`, `asset`, fresh `quote_t`, positive `price`, `entry_price`, `initial_quantity`, remaining `quantity`, and actual `tp_filled_quantity`. After half is filled, `peak_since_tp` must include the current price and the persisted maximum since take-profit. The connector owns and persists this peak and confirmed fills, including across restarts.

All endpoints refuse operation without `SITE_PASSWORD`. Decision/receipt deduplication and recent learner memory survive restart in atomic `copytrading/account-learner.json`. Journals retain up to 10,000 IDs and fail closed when full rather than silently forgetting old receipts.

**There is no connected signal collector or real order executor yet.** These endpoints are private integration points, not an autonomous trading loop. No funds are spent by this change. Before submission an executor must verify current holdings/quotes, reserve pending entries against budget, deduplicate pending exits, reconcile receipts and account metrics, and handle slippage and fees. Stops are triggers for proposals, not guaranteed execution prices. The public player honestly reports execution as not connected.

## Validation

`python -m pytest tests/test_account_planner.py tests/test_x_embed.py -q` covers entry budgets, risk guards, learning and restart deduplication, exit boundaries, partial take-profit fills, confirmed-fill trailing activation, stale data, public redaction and private-route isolation. Chrome visual QA covers the orange square player and fallback at 480 × 480.

## Funded Solana runner follow-up

The owner subsequently supplied a private wallet key, Helius RPC credential and a third-party Fomo data API key and authorized a $5 buy/sell test and copying new buys from the seven followed traders. A real SOL roundtrip succeeded; the Helius sell appeared on Fomo. The initial gasless Jupiter buy did not appear in the observed Fomo history. External trade visibility is therefore not guaranteed for every route.

`copytrading.runner` is an explicit opt-in process, separate from the room brain. Install `requirements-copytrading.txt` and invoke `python -m copytrading.runner --private-config <owner-only JSON outside Git> --watchlist <resolved wallet JSON> --data-dir <room data directory> --execute`. Without `--execute` it observes without submitting. The private config must also set `enabled:true`, the exact authorized `budget_usd:100`, `per_trade_usd:5`, a raw `private_key` (base58 or 64-byte array; a key in the former `seed_phrase` field is accepted for compatibility), matching `expected_fomo_wallet_address`, and `helius_rpc_url` or a bare Helius key. Mnemonic phrases are not supported by this raw-key loader. Optional Jupiter API key; current Jupiter keyless access is paced at one request per 2.1 seconds.

The third-party Fomo API is used only to resolve the owner's actual following list and Solana wallet identities. Its credential is never shared with Helius or Jupiter; wallet secrets are never shared with the data provider. The runner receives confirmed Helius `logsSubscribe` events for the resolved wallet watchlist. Only successful fresh swap-like buys (15s age limit, startup cutoff, one unambiguous non-base token increase and an actual USDC/SOL debit) can trigger entries. Transfers, failed transactions, historical transactions and other chains are excluded. The initial watchlist is a snapshot of the seven verified follows, not continuous Fomo-follow synchronisation.

Each accepted signal buys $5 USDC worth, with $100 aggregate remaining cost exposure and four open positions maximum. Duplicate source signatures, already held mints, pre-existing holdings, insufficient cash, unsupported tokens or failed simulation hold the entry. This mode copies eligible followed buys directly; the room brain's adaptive selection is not the order gate. The runner does not claim native brain credit learning for these orders.

Jupiter `/build` supplies exact-input swap instructions; Helius sends and confirms the signed transaction. Before signing, the runner validates intent, 1% slippage ceiling, signer, legacy SPL mint with no freeze authority, simulated owner balances, gas/rent debit, unchanged token authorities/delegates, correct input debit and minimum output. Token-2022 assets are excluded in this version. Insufficient gas causes a held entry; it does not silently make an additional SOL purchase.

The take-profit sells half the original quantity at +100%, confirmed sale quantities unlock a persisted 10% trailing peak, and -75% stop sells remaining quantity. Exit triggers use a fresh executable USDC quote, not a guaranteed fill price. Receipt quantities and actual USDC changes reconcile positions. A private process lock prevents two runners sharing state. Persistent pending signatures are reconciled on restart; uncertain transactions halt new submissions rather than repeating orders. Confirmed trades and a short heartbeat are written to the existing public snapshot contract, with credentials excluded. Quotes or RPC failures may delay exits. No chain or app stream can guarantee copying in the same transaction as the source trader.

The initial runtime and public preview use the owner's Mac. They depend on it staying awake and connected. The public quick-tunnel URL is temporary; a permanent server deployment and browser-screen stream remain separate work. The desk monitor remains an explicitly labelled reviewed still, while confirmed execution rows are live. The runner starts only when explicitly launched; merging this code does not start it on Railway.

### Real Fomo tab monitor

`browser_bridge/extension` is an opt-in Chrome MV3 tab-capture bridge. The owner
loads the unpacked extension and starts it from the dedicated Fomo account's
token tab. Authentication remains inside Chrome. Neither Fomo cookies nor wallet
credentials are transferred to the bridge. Only canonical Fomo Solana token
pages pass the source guard; visible dialogs, menus and authentication fields
pause publishing. The runner writes a display intent for each fresh detected
buy, and the extension navigates its captured tab to that actual token page.

The receiver runs on loopback port 8878 with a separate random bearer token.
Start with `python -m browser_bridge.server --config <private-bridge-config>
--data-dir <data-dir>`. Copy the private config as `config.json` in the local
extension directory; never commit it. With `SUB01_FOMO_LIVE=1`, the public monitor
accepts fresh validated frames only and blanks after four seconds without a
frame. It does not fall back to the old capture. Enlargement uses the same live
frames. The owner can stop transmission from the extension.

Chrome activation and a real tab-capture session remain required. Automated
checks cover authentication, source URL restrictions, frame integrity and expiry;
they do not establish that Chrome tab capture has been activated. The current
local receiver and temporary public tunnel require this computer to stay awake.
