let stream=null, stopped=false;
const video=document.getElementById('video'),canvas=document.getElementById('canvas');
chrome.runtime.onMessage.addListener((message,sender,reply)=>{
  if(message.target!=='offscreen'||message.type!=='capture')return;
  (async()=>{
    stream=await navigator.mediaDevices.getUserMedia({audio:false,video:{mandatory:{chromeMediaSource:'tab',chromeMediaSourceId:message.streamId}}});
    video.srcObject=stream;await video.play();
    stream.getVideoTracks()[0].onended=()=>{stopped=true;};
    const tick=async()=>{
      if(stopped)return;
      try{
        const gate=await chrome.runtime.sendMessage({type:'guard'});
        if(gate?.safe&&video.videoWidth&&video.videoHeight){
          const scale=Math.min(1,1920/video.videoWidth,1080/video.videoHeight);
          canvas.width=Math.round(video.videoWidth*scale);canvas.height=Math.round(video.videoHeight*scale);
          canvas.getContext('2d').drawImage(video,0,0,canvas.width,canvas.height);
          // Recheck immediately before publishing; a navigation or modal fails closed.
          const second=await chrome.runtime.sendMessage({type:'guard'});
          if(second?.safe&&second.url===gate.url){
            const jpeg=await new Promise(resolve=>canvas.toBlob(resolve,'image/jpeg',.8));
            await fetch('http://127.0.0.1:8878/frame',{method:'POST',headers:{Authorization:'Bearer '+message.config.token,'Content-Type':'image/jpeg','X-Fomo-Page':gate.url},body:jpeg,signal:AbortSignal.timeout(1500)});
          }
        }
      }catch{}
      setTimeout(tick,750);
    };tick();return {message:'Capturing'};
  })().then(reply).catch(e=>reply({error:e.message}));return true;
});
