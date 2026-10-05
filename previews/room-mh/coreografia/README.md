# Alzarsi dalla scrivania e andare via (preview/room-mh, #98)

Prima = preview/room-mh 1b6533e (si alza sul posto, gira di 180° fermo, rimette la sedia, braccia smorzate).
Dopo = preview/room-mh 0b6efe3. Niente live, niente merge.

- `alzarsi_confronto.jpg` — da guardare per primo: gli stessi momenti (seduto, si alza, in piedi, primo passo, gira camminando, cammina) in Prima | Dopo | Reale.
- `1_alza_finestra.mp4`, `5_notte_alza.mp4` — 8 s, camera ferma, Prima | Dopo | Reale, allineati sull'inizio dell'alzata.
- `prima_dopo_1280x800.mp4` (+ json) — il render GPU completo; `pod_log.txt` — il pod (A5000, 4.6 min, ~$0.02, cancellato).

## Cosa cambia

- Una sola ripresa mocap (22_Stretch_Stand_And_Walk) dall'alzata al primo passo: seduto arretra con la sedia girandola, si alza (le gambe la spingono ancora un po'), gira mentre cammina (2–4 passi) e il passo continua senza fermarsi. Specchiata quando esce a destra.
- La sedia resta dove la spingono le gambe (clip 5: indietro di 37 cm, ruotata di 60°). Eccezione proposta, opzione (a) del coordinatore, da approvare: per il davanzale (raggiungibile solo dal varco di 30 cm dietro la sedia) la spinge sotto la scrivania con una mano mentre passa, 0.35 s di contatto, poi rotola da sola; lui non si ferma.
- Camminata come registrata: niente più smorzamento delle braccia.

## Misure (camminata nella stanza, gradi)

| | ginocchio in appoggio | ginocchio in volo | gomito |
|---|---|---|---|
| Prima | 14–16 (max 22) | 64 | 3 (sx) / 10 (dx), quasi fermi |
| Dopo | 12–16 (0–21) | 65 | 8–32, media 16 |

Le ginocchia erano già come la sorgente (il corpo MakeHuman non ha IK dei piedi); i gomiti erano rigidi per lo smorzamento al 10 %, ora oscillano come nel mocap.

Penetrazioni (probe fotogramma per fotogramma, software WebGL): clip 5 zero con scrivania, sedia e letto in tutta l'alzata e la camminata; clip 1 un fotogramma con 5 vertici dell'avambraccio sulla sedia mentre la spinge e uno con 17 vertici di un alluce sul bordo del letto vicino al davanzale.

## Riferimento reale

"A Man Walking Away after Sitting on a Chair", PNW Production, Pexels video 8377765 (licenza Pexels: uso gratuito, modifiche consentite), 16.5–24.5 s, 640×360; il volto è coperto a mosaico in ogni fotogramma in cui è visibile. Solo su questo branch di anteprime, non nel codice. Per il gesto di spingere la sedia non ho trovato un video Pexels/CC0 adatto.
