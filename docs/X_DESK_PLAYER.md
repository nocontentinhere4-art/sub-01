# SUB-01 desk player for X

The player shows a fixed over-the-shoulder view of the existing character at the desk. It is a presentation view, not a claim about the character's current activity. The monitor and operation list are driven by the same public status response. No viewer can place an order through the player.

## Enable after visual review

Set `SUB01_X_EMBED=1` and `SUB01_PUBLIC_URL=https://your-public-origin` on the existing server. The share link is `/share/sub01`; it declares an X Player Card with a 480 × 480 iframe at `/embed/sub01` and a static PNG fallback. Public HTTPS and an actual X card test are required. X may restrict interactive cards or show only the fallback. Local browser rendering is not proof of acceptance by X.

The existing password gate remains on `/`, `/ws`, private APIs, and all original room assets. Only exact GET/HEAD player routes and selected assets become public. This switch is off by default. Existing CDN-hosted Three.js 0.169 is reused. The player renders at at most 30 fps, caps pixel density, pauses rendering/polling when hidden, and shares the server state rather than starting a new brain.

## Actual Fomo account — pending integration

There is currently no connected Fomo account, trade executor, authenticated browser mirror, or chain verifier in this change. No real order is submitted and no funds are spent. The monitor explicitly says the account is not connected. Paper replay files are never displayed as real executions.

A future **trusted server-side account connector** may atomically write `data_dir/embed/fomo.json` with this contract:

- `version: 1`, `provider: "fomo"`, `mode: "real"`;
- `connected`: boolean; `updated_at`: Unix seconds from the connector heartbeat;
- `executions`: rows with `side` (`buy`/`sell`), `asset` (public symbol), `amount` (positive token quantity), `status: "confirmed"`, and `tx` (Solana transaction signature).

Only these public execution fields are exposed, at most eight rows. The reader caps the file at 256 KiB, ignores incompatible/paper records, invalid symbols/signatures/amounts, pending records, and duplicate transactions. A heartbeat older than 60 seconds makes the account offline. Transaction links allow viewers to inspect receipts; the reader itself does not establish confirmation or ownership on chain. The UI calls confirmations *reported* by the account connector.

The owner explicitly authorized publicly displaying tokens, buys/sells, amounts and transaction links in this chat. Account cookies, wallet identifiers, credentials and arbitrary extra fields are excluded. Never place cookies in the player, URL, committed files or this snapshot. The actual Fomo browser UI is not mirrored; the monitor is a SUB-01 status panel awaiting connection.

Before funded operation, connect the dedicated account through a private server-side integration and establish the owner's funding and per-order limits. Those are separate from preparing this public view.

## Validation

`python -m pytest tests/test_x_embed.py -q` checks opt-in behavior, the public route allowlist, private routes remaining gated, invalid origins, redaction, missing/malformed account files, paper-mode rejection, and stale heartbeat behavior. Chrome visual QA covers the square card at 480 × 480.

## Browser screen follow-up

The owner requested the actual Fomo page, including charts and the dedicated account. The existing Chrome profile @iswizy is explicitly not the SUB-01 account. No cookies were exported or received. A private empty cookie file was prepared outside this repository; never commit it. The public player still uses its status panel. An arbitrary JPEG-to-public endpoint was rejected by automatic review, including after scoped screen-sharing approval, because it did not enforce cropping/redaction in code. It was not added. A future screen bridge must apply and verify cropping/redaction before publishing and must keep login, settings and unrelated private data out of the stream.

## Reviewed Fomo frame preview

A narrow read-only `/embed/fomo-frame.jpg` route now supports one exact reviewed JPEG at `data_dir/embed/fomo-reviewed-frame.jpg`, enabled only when its SHA-256 matches `SUB01_FOMO_FRAME_SHA256`. New/arbitrary screenshots are never exposed automatically. The frame is bounded to 4 MiB and 1080p and verified as JPEG; missing, invalid or changed files fail closed. The player labels it as a captured preview, not a live screen stream. Browser login has been observed in Chrome on the dedicated account, now renamed SUBZERONE01. The owner additionally authorized public nickname and balance display; cookies/security dialogs remain private. The actual frame and cookie files are not committed. A continuing live browser bridge is still required.
