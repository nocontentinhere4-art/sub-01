# room/desk_states: the seated states' own clips (room.html?char=mixamo&anim=sova)

One GLB per slot of `room/desk_states.js` (`SLOTS`), named for the slot (`idle_b.glb`, `react_win.glb`, ...), each with
one animation on `room/char_mixamo.glb`'s skeleton (`mixamorig:*`; `char_mixamo.js` `fixClip` takes it as it takes the
clips in `room/mh_mx/`), seated on our chair as those are. A slot plays its own GLB once its name is in `index.json`
(`{"clips": ["idle_b", ...]}`); until then it plays its stand-in from `room/mh_mx/`. Empty for now: no clip here until
its licence is cleared.
