// STUB fx (core stream). The fx stream replaces this file; keep the exports.
//
// createFx(renderer, scene, camera, data, quality) ->
//   {rain(msg), innerLine(speech), weather(market), update(dt, env), render(), resize(w, h)}
//   rain(msg)          accepted chat message ({text, nick, regions, networks, cid, ...}): falls as orange rain made of
//                      its own words and lands on the districts in msg.regions (main.js also flashes them in the city)
//   innerLine(speech)  speech message ({text, kind, about, ...}) + speech.chat = the chat message it answers (when
//                      speech.about matches a chat cid), else null: the inner line shown where the words landed
//   weather(market)    "pumping" | "dumping" | "choppy" | "calm": warm pulses / glitches / distortion
//   update(dt, env)    env.replays = [{text, t, seq}] (REM replays of the day's messages), env.stage, env.night...
//   render()           draws the frame; the fx stream owns post-processing (bloom, glitch, warp). Stub: plain render.
//   resize(w, h)       called by main.js when the canvas size changes
export function createFx(renderer, scene, camera, data, quality) {
  return {
    rain() {},
    innerLine() {},
    weather() {},
    update() {},
    render() { renderer.render(scene, camera); },
    resize() {},
  };
}
