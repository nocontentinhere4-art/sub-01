"""Title corpus for reviewing chat.INCITE_RE / chat.incitement (review G24, branch preview/review-main).

BENIGN: real song, film, game, YouTube, news and tutorial titles. Many use violent verbs innocently ("kill", "shoot",
"fight", "bomb", "attack", "drop", "fire", "explode"), sometimes next to a word that is also in chat.GROUPS
("Japanese", "Chinese", "Roma", "women", ...). None of them is a call to violence against a group, so all of them
should pass.
INCITING: explicit calls to violence against a group, i.e. titles the owner's rule ("explicit calls to violence
against a group are refused") says must be refused. A few are real, widely reported chants or song titles
("Kill the Boer", "Death to Arabs"). The rest are realistic phrasings (spelling, inflection, hyphen and hashtag,
Italian and Spanish variants), because real hate titles are not something to collect. NATION: "death to <country>"
chants, kept as a separate class because whether they count is the owner's call.
"""

BENIGN = [
    # --- songs, English
    "Kill Bill", "Killing in the Name", "Killing Me Softly with His Song", "Kill the Lights", "Kill Em with Kindness",
    "Kill This Love", "Killer Queen", "Mr. Brightside", "Kill of the Night", "Kill the DJ", "Kill All Hippies",
    "Kill the Poor", "Kill the Rich", "Kill Your Darlings", "Kill My Vibe", "Shoot to Thrill", "I Shot the Sheriff",
    "Bang Bang (My Baby Shot Me Down)", "Shoot the Runner", "Shoot to Kill", "Shooting Stars", "Shooting Star",
    "Fight for Your Right", "Fight Song", "The Fight", "Fighter", "Bombtrack", "Bombs Away", "Da Bomb", "The Bomb",
    "Attack", "Attack Attack!", "Heart Attack", "Drop It Like It's Hot", "Drop the World", "Don't Drop That Thun Thun",
    "Fire Burning", "Set Fire to the Rain", "We Didn't Start the Fire", "Girl on Fire", "Light My Fire", "Ring of Fire",
    "Burn", "Burn It Down", "Burn the Witch", "Burnin' Up", "Explode", "Exploder", "Gun", "Gunpowder & Lead",
    "Murder on the Dancefloor", "Smooth Criminal", "Psycho Killer", "Hang the DJ (Panic)", "Hang Me Up to Dry",
    "Hanging by a Moment", "Death to Everyone", "Death of a Bachelor", "Stockholm Syndrome", "Price Tag",
    "I Heard It Through the Grapevine", "Skyscraper", "Sexual Healing", "Weapon of Choice", "Cannibal", "Scandal",
    "Give It 2 Me", "Woodstock", "Women (Def Leppard)", "Independent Women, Pt. 1", "Russians (Sting)",
    "Turning Japanese", "Chinese Democracy", "Indians (Anthrax)", "Asian Girlz", "Gypsies, Tramps & Thieves",
    "Mexican Radio", "Big in Japan", "Death to the Hypocrites",
    "Top Hits 2000 - 2010 Mix",
    # --- songs, Italian
    "Fuoco nel fuoco", "Bomba o non bomba", "La guerra di Piero", "Uccidete la luna di marzo", "Il cielo in una stanza",
    "Inno Nazionale Italiano", "Sparami (Lo-Fi)", "Fai rumore", "Brucia la città", "Uccidimi (Vasco)",
    "Il ballo del qua qua", "Volare", "Ignazio Boschetto - Il Volo live", "Sparare alla luna",
    # --- songs, Spanish
    "La Bomba", "Fuego", "Mátame", "Dispárame, dispara", "Bombón", "Explota mi corazón", "Fuego de noche, nieve de día",
    "Matador", "La Bamba", "Despacito", "Quémalo", "Pégale", "Gasolina", "Quiero que me mates",
    # --- films, TV, games
    "Kill the Irishman (2011) Trailer", "Shoot 'Em Up (2007) Trailer", "Fight Club (1999) Official Trailer",
    "Texas Chainsaw Massacre Gameplay", "Killing Floor 2 Gameplay", "Suicide Squad Trailer",
    "Call of Duty: Kill Confirmed", "Fortnite Kill Compilation #12", "Minecraft but I Can't Stop Killing",
    "How to Kill the Ender Dragon in 5 Minutes", "Elden Ring - How to Kill Malenia", "Attack on Titan Opening",
    "Kill Russians in Arma 3 - Cold War Mod", "Shoot the Chinese Dragon Boss - Wo Long", "Battlefield 1 Bomb Run",
    "Valorant Ace - Drop the Spike", "CS2: Bomb Defuse Clutch", "Hitman: Kill Everyone Challenge",
    # --- tutorials, gardening, cooking, photography
    "How to Kill Japanese Beetles Naturally", "How to Kill Japanese Knotweed for Good", "Kill Chinese Privet Fast",
    "How to Shoot Japanese Street Photography", "How I Shoot Women's Portraits with Natural Light",
    "How to Shoot Chinese New Year Fireworks", "Burn Chinese Lanterns Safely?", "Shoot Indians Cricket Highlights",
    "How to Kill Weeds in Your Lawn", "How to Kill Fruit Flies in 2 Minutes", "Fire Drill Training Video",
    "How to Drop Ship in 2026", "Fire Your Boss: Freelance Guide", "Bomb Pop Recipe", "Bath Bomb DIY",
    "How to Fight a Bear (Don't)", "Fire Safety for Kids", "Cooking with Fire - Japanese BBQ",
    "Gas the Car Up: Road Trip Vlog", "Hang Drywall Like a Pro", "Hang Christmas Lights Without Nails",
    "Kill the Whites of Your Laundry Stains (Old Hack)",
    # --- news / sport
    "Lazio slaughter Roma 3-0 in the derby", "Police shoot suspect after chase", "Ukraine strikes kill Russians at base",
    "Gas prices drop again", "Bomb threat closes school", "Women's World Cup Final Highlights",
    "Murder Mystery 2 (Netflix) Review", "How the Japanese Fight Earthquakes", "Mexicans Fight for Water Rights",
    "Death to 2020 (Netflix) Trailer", "Kill the Messenger (2014) Trailer",
    # --- vlogs, misc YouTube
    "I Tried to Kill My Phone Addiction", "Killing It at the Gym", "Shooting Hoops with the Boys", "Dropping My New Album",
    "This Song Is Fire 🔥", "Exploding Watermelon Challenge", "Attack of the Killer Tomatoes Review",
    "Japanese Kill Bill Sword Scene Breakdown", "Kill Time in Tokyo: 10 Things to Do", "Kill the Noise - Live Set",
]

INCITING = [
    # real, widely reported chants / titles
    "Kill the Boer", "Death to Arabs",
    "Shoot the Boer",
    # plain English phrasings the regex intends to catch
    "Kill All Jews", "Gas the Jews", "Death to Muslims", "Kill the Gays", "Hang All Immigrants", "Burn the Refugees",
    "Exterminate the Roma", "Death to all Christians", "Lynch the Blacks",
    # spelling and punctuation variants
    "K1ll all J3ws", "kill-all-jews", "#KillAllMuslims", "Kill_the_gays", "kill/the/immigrants", "death 2 jews",
    "Kill all of the Muslims",
    # inflections and word order
    "Killing all the Jews", "Kill every Jew", "Kill every immigrant", "Kill every woman", "Kill every gay",
    "Muslims must die", "All Jews should be killed", "Gays deserve death", "Shoot every Mexican", "Kill every Muslim",
    # other verbs
    "Nuke the Muslims", "Bomb the Jews", "Stab the Immigrants", "Massacre the Christians", "Wipe out the Roma",
    "Behead the Christians",
    # Italian and Spanish
    "Uccidete tutti gli ebrei", "Morte ai musulmani", "Morte agli immigrati", "Matar a todos los judíos",
    "Muerte a los gitanos",
]

NATION = ["Death to America", "Death to Israel", "Death to Russia"]
