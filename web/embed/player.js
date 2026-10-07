import * as THREE from 'three';
import {GLTFLoader} from 'three/addons/loaders/GLTFLoader.js';
import {MeshoptDecoder} from 'three/addons/libs/meshopt_decoder.module.js';
import {RoomEnvironment} from 'three/addons/environments/RoomEnvironment.js';
import {prep, fixClip} from './character.js';

const $ = id => document.getElementById(id);
let mixer, renderer, scene, camera, idle;
const clock = new THREE.Clock();
let updateMonitor=()=>{}, screenMaterial=null, screenStamp=null, screenBusy=false;
function fail() {
  $('loading').replaceChildren(document.createTextNode('The desk could not load. '));
  const b = document.createElement('button'); b.id = 'retry'; b.textContent = 'Retry';
  b.onclick = () => location.reload(); $('loading').append(b);
}
async function boot() {
  renderer = new THREE.WebGLRenderer({antialias:true, powerPreference:'low-power'});
  renderer.setPixelRatio(Math.min(devicePixelRatio,1.25)); renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping; renderer.toneMappingExposure = 1.2;
  $('view').append(renderer.domElement);
  scene = new THREE.Scene(); scene.background = new THREE.Color('#110e0b');
  const pm = new THREE.PMREMGenerator(renderer), env = new RoomEnvironment();
  const envTarget = pm.fromScene(env); scene.environment = envTarget.texture; scene.environmentIntensity = .35; env.dispose(); pm.dispose();
  scene.add(new THREE.HemisphereLight(0xfff1dd,0x1a2520,1.1));
  const sun = new THREE.DirectionalLight(0xffe2c0,2); sun.position.set(0,5,3); scene.add(sun);
  camera = new THREE.PerspectiveCamera(38,1,.05,40);
  // Fixed portrait over his right shoulder; the rest of the room stays off camera.
  camera.position.set(.65,2.15,1.55); camera.lookAt(-1.02,1.23,-.75);
  const loader = new GLTFLoader().setMeshoptDecoder(MeshoptDecoder);
  const [room, char, watch] = await Promise.all(['room.glb','character.glb','idle.glb'].map(n=>loader.loadAsync('/embed/assets/'+n)));
  scene.add(room.scene); const conv = prep(THREE,char); scene.add(char.scene);
  const clip = fixClip(THREE,watch.animations[0],conv);
  mixer = new THREE.AnimationMixer(char.scene); idle = mixer.clipAction(clip); idle.play(); mixer.update(0);
  // Anchor the actual hips, rather than relying on the source rig's root axes.
  const hip = char.scene.getObjectByName('Hips'); const local = hip.getWorldPosition(new THREE.Vector3());
  const heading = -2.85; char.scene.rotation.y = heading;
  local.applyAxisAngle(new THREE.Vector3(0,1,0),heading);
  char.scene.position.set(-1.12-local.x,.735-local.y,-.56-local.z);
  // Monitor starts with status; an exact reviewed Fomo capture may replace it.
  const marker = room.scene.getObjectByName('SURF_monitor');
  const cv = document.createElement('canvas'); cv.width=768; cv.height=448; const g=cv.getContext('2d');
  const tex = new THREE.CanvasTexture(cv); tex.colorSpace=THREE.SRGBColorSpace;
  function monitor(state) {
    g.fillStyle='#17110d';g.fillRect(0,0,768,448);g.fillStyle='#ff6a00';g.font='bold 44px monospace';g.fillText('FOMO / SUB-01',32,70);
    g.fillStyle='#ff9a3c';g.font='22px monospace';g.fillText(state?.fomo?.connected?'ACCOUNT CONNECTED':'ACCOUNT NOT CONNECTED',32,112);
    const rows=state?.trading?.operations||[];
  if(!rows.length){g.fillStyle='#ff6a00';g.fillText('WAITING FOR FOMO',32,220);g.fillStyle='#ff9a3c';g.fillText('Account not connected',32,265);}
    rows.slice(-4).forEach((r,i)=>{g.fillStyle='#ff6a00';g.fillText((r.action==='buy'?'BUY ':'SELL ') +(r.asset||'') ,32,190+i*48);});
    g.fillStyle='#ff9a3c';g.font='18px monospace';g.fillText(state?.fomo?.connected?'Account execution feed':'Waiting for account connection',32,425);tex.needsUpdate=true;
  }
  monitor(null); updateMonitor=monitor; screenMaterial=new THREE.MeshBasicMaterial({map:tex});
  if(marker){room.scene.updateMatrixWorld(true);const u=marker.userData;
    const screen=new THREE.Mesh(new THREE.PlaneGeometry(u.w||.68,u.h||.4),screenMaterial);
    marker.getWorldPosition(screen.position); marker.getWorldQuaternion(screen.quaternion);
    screen.position.add(new THREE.Vector3(0,0,.003).applyQuaternion(screen.quaternion));scene.add(screen);}
  $('loading').hidden=true;
  const resize=()=>{const r=$('view').getBoundingClientRect();camera.aspect=r.width/Math.max(r.height,1);camera.updateProjectionMatrix();renderer.setSize(r.width,r.height,false);};
  new ResizeObserver(resize).observe($('view')); resize();
  let last=0;function frame(t){requestAnimationFrame(frame);if(document.hidden||t-last<1000/30)return;last=t;mixer.update(Math.min(clock.getDelta(),.05));renderer.render(scene,camera);}requestAnimationFrame(frame);

}

function update(data){
  const s=data.trading, connected=data.fomo.connected, rows=s.operations;
  const rules=data.strategy?.rules;
  $('rules').textContent=rules ? `${rules.budget_usd===null?'BUDGET PENDING':'$'+rules.budget_usd+' / $'+rules.per_order_usd+' ENTRY'} · ½ AT +100% · TRAIL 10% · SL −75%` : '';
  const plan=data.strategy?.last;
  $('strategy').textContent=plan?`NEXT: ${plan.action==='buy'?'COPY '+plan.asset:'HOLD CASH'} · ${plan.reason}`:'Copy-trading · '+(data.strategy?.state||'waiting for feed');
  if(data.monitor?.available)loadFrame(data.monitor);else updateMonitor(data);
  $('badge').textContent=connected?'THE DESK · CONNECTED':'THE DESK · OFFLINE';
  $('mode').textContent=connected?'ACCOUNT EXECUTIONS':'ACCOUNT NOT CONNECTED';
  $('status').textContent=connected?'Fomo account feed · reported confirmations':s.updated_at?'Account offline · showing last received operations':'Waiting for Fomo account · no real operations yet';
  if(data.monitor?.available){$('badge').textContent='THE DESK · FOMO PREVIEW';$('mode').textContent='REVIEWED SCREEN';$('status').textContent='Fomo account screen · captured preview';}
  if(!rows.length){$('ops').replaceChildren(Object.assign(document.createElement('div'),{className:'empty',textContent:data.monitor?.available?'No operations received.':connected?'No confirmed operations received yet.':'Account not connected. Real operations will appear here.'}));return;}
  $('ops').replaceChildren(...rows.slice().reverse().map(r=>{
    const row=document.createElement('div');row.className='row';
    const action=document.createElement('span');action.className='buy';action.textContent=`${r.action.toUpperCase()} ${r.asset}`;
    const amount=document.createElement('span');amount.textContent=String(r.amount);
    const tx=document.createElement('a');tx.textContent='TX ↗';tx.href='https://solscan.io/tx/'+r.tx;tx.target='_blank';tx.rel='noopener noreferrer';tx.style.color='#ff9a3c';
    row.append(action,amount,tx);return row;
  }));
}

async function loadFrame(meta){
  if(!screenMaterial||screenBusy||screenStamp===meta.revision)return;
  screenBusy=true;
  try{
    const res=await fetch('/embed/fomo-frame.jpg',{credentials:'omit',cache:'no-store',signal:AbortSignal.timeout(8000)});
    if(!res.ok)throw Error();
    const bitmap=await createImageBitmap(await res.blob(),{imageOrientation:'flipY'});
    const tex=new THREE.CanvasTexture(bitmap);tex.colorSpace=THREE.SRGBColorSpace;
    const old=screenMaterial.map;screenMaterial.map=tex;screenMaterial.needsUpdate=true;screenStamp=meta.revision;
    if(old){old.image?.close?.();old.dispose();}
  }catch{$('status').textContent+=' · screen unavailable';}
  finally{screenBusy=false;}
}

async function poll(){
  if(!document.hidden){try{const res=await fetch('/embed/state',{credentials:'omit',cache:'no-store',signal:AbortSignal.timeout(8000)});if(!res.ok)throw Error();update(await res.json());}catch{$('status').textContent='Connection lost · displayed operations may be old';}}
  setTimeout(poll,3000);
}
boot().then(poll).catch(e=>{console.error('Desk failed',e);fail();poll();});
