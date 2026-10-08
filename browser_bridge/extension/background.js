const TOKEN_URL=/^https:\/\/fomo\.family\/tokens\/solana\/[1-9A-HJ-NP-Za-km-z]{32,44}\/?$/;
let sourceTab=null, lastIntent=null;
async function guard(){
  if(sourceTab===null)return {safe:false};
  try{
    const tab=await chrome.tabs.get(sourceTab);
    if(!TOKEN_URL.test(tab.url||'')||tab.status!=='complete')return {safe:false};
    const result=await chrome.scripting.executeScript({target:{tabId:sourceTab},func:()=>{
      const visible=e=>!!(e.getClientRects().length&&getComputedStyle(e).visibility!=='hidden');
      const blocked=[...document.querySelectorAll('[role="dialog"],dialog[open],[role="menu"],[data-radix-popper-content-wrapper],input[type="password"],input[autocomplete="one-time-code"]')].some(visible);
      const text=document.body?.innerText||'';
      const sensitive=/recovery phrase|seed phrase|private key|reveal secret|backup your wallet|enter your password|verify your identity|sign in to fomo|log in to fomo/i.test(text);
      return {safe:!blocked&&!sensitive&&document.readyState==='complete'};
    }});
    return {safe:result[0]?.result?.safe===true,url:tab.url};
  }catch{return {safe:false};}
}
async function stop(){sourceTab=null;lastIntent=null;if(await chrome.offscreen.hasDocument())await chrome.offscreen.closeDocument();return {message:'Live monitor stopped'};}
async function start(){
  const [tab]=await chrome.tabs.query({active:true,currentWindow:true});
  if(!tab||!TOKEN_URL.test(tab.url||''))throw Error('Open a Fomo token on the SUB-01 account first.');
  await stop();sourceTab=tab.id;
  if(!(await guard()).safe){sourceTab=null;throw Error('Close dialogs and login panels before sharing.');}
  const config=await (await fetch(chrome.runtime.getURL('config.json'))).json();
  await chrome.offscreen.createDocument({url:'offscreen.html',reasons:['USER_MEDIA'],justification:'Stream only the authorized SUB-01 Fomo tab to the public monitor.'});
  const streamId=await chrome.tabCapture.getMediaStreamId({targetTabId:tab.id});
  const response=await chrome.runtime.sendMessage({target:'offscreen',type:'capture',streamId,config});
  if(response?.error){await stop();throw Error(response.error);}
  return {message:'Live Fomo monitor started. Keep this browser open.'};
}
async function follow(){
  if(sourceTab===null)return {safe:false};
  const current=await guard();if(!current.safe)return current;
  try{
    const config=await (await fetch(chrome.runtime.getURL('config.json'))).json();
    const res=await fetch('http://127.0.0.1:8878/intent',{headers:{Authorization:'Bearer '+config.token},cache:'no-store'});
    if(res.ok){const intent=await res.json();if(intent.mint&&intent.revision!==lastIntent){lastIntent=intent.revision;await chrome.tabs.update(sourceTab,{url:'https://fomo.family/tokens/solana/'+intent.mint});return {safe:false};}}
  }catch{}
  return guard();
}
chrome.runtime.onMessage.addListener((message,sender,reply)=>{
  if(message.target==='offscreen')return;
  if(sender.id!==chrome.runtime.id){reply({error:'Denied'});return;}
  const task=message.type==='start'?start:message.type==='stop'?stop:message.type==='guard'?follow:null;
  if(!task)return;
  task().then(reply).catch(e=>reply({error:e.message}));return true;
});
