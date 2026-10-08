import cv2, json, sys, numpy as np, mediapipe as mp
src, out = sys.argv[1], sys.argv[2]
cap = cv2.VideoCapture(src); fps = cap.get(cv2.CAP_PROP_FPS) or 120; step = max(1, round(fps/30))
hands = mp.solutions.hands.Hands(static_image_mode=False, max_num_hands=2, model_complexity=1, min_detection_confidence=0.4, min_tracking_confidence=0.4)
pose = mp.solutions.pose.Pose(static_image_mode=False, model_complexity=1)
F = {'thumb':[1,2,3,4],'index':[5,6,7,8],'middle':[9,10,11,12],'ring':[13,14,15,16],'pinky':[17,18,19,20]}
def ang(a,b): a=a/np.linalg.norm(a); b=b/np.linalg.norm(b); return float(np.degrees(np.arccos(np.clip(a@b,-1,1))))
frames=[]; i=0
while True:
    ok, img = cap.read()
    if not ok: break
    if i % step: i+=1; continue
    rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    h = hands.process(rgb); p = pose.process(rgb)
    rec={'t': round(i/fps,3), 'hands':[]}
    pw = p.pose_world_landmarks.landmark if p.pose_world_landmarks else None
    if h.multi_hand_world_landmarks:
        for lm, hd in zip(h.multi_hand_world_landmarks, h.multi_handedness):
            P=np.array([[q.x,q.y,q.z] for q in lm.landmark]); side=hd.classification[0].label
            fin={}
            for n,(a,b,c,d) in F.items():
                v0=P[a]-P[0]; v1=P[b]-P[a]; v2=P[c]-P[b]; v3=P[d]-P[c]
                flex=[ang(v0,v1),ang(v1,v2),ang(v2,v3)]
                nrm=np.cross(v1,v2); side_bend=0.0
                if np.linalg.norm(nrm)>1e-6:
                    nrm/=np.linalg.norm(nrm); side_bend=float(np.degrees(np.arcsin(np.clip(abs(v3/np.linalg.norm(v3)@nrm),0,1))))
                fin[n]={'flex':[round(x,1) for x in flex],'side':round(side_bend,1)}
            spread=ang(P[5]-P[0],P[17]-P[0])
            wrist=None
            if pw:
                e,w = (13,15) if side=='Left' else (14,16)   # mediapipe mirror: label is as seen; both kept
                fa=np.array([pw[w].x-pw[e].x,pw[w].y-pw[e].y,pw[w].z-pw[e].z]); hv=P[9]-P[0]
                wrist=round(ang(fa,hv),1)
            rec['hands'].append({'side':side,'fingers':fin,'spread':round(spread,1),'wrist_bend':wrist})
    frames.append(rec); i+=1
summ={}
for side in ('Left','Right'):
    hs=[hh for f in frames for hh in f['hands'] if hh['side']==side]
    if not hs: continue
    d={'frames':len(hs)}
    for n in F:
        fl=np.array([hh['fingers'][n]['flex'] for hh in hs]); sb=np.array([hh['fingers'][n]['side'] for hh in hs])
        d[n]={'flex_p5':np.percentile(fl,5,0).round(1).tolist(),'flex_p50':np.percentile(fl,50,0).round(1).tolist(),'flex_p95':np.percentile(fl,95,0).round(1).tolist(),'side_p50':round(float(np.median(sb)),1),'side_p95':round(float(np.percentile(sb,95)),1)}
    wb=[hh['wrist_bend'] for hh in hs if hh['wrist_bend'] is not None]
    if wb: d['wrist_bend_p5_p50_p95']=np.percentile(wb,[5,50,95]).round(1).tolist()
    d['spread_p5_p50_p95']=np.percentile([hh['spread'] for hh in hs],[5,50,95]).round(1).tolist()
    summ[side]=d
json.dump({'source':'owner reference video (not stored), 30 fps samples, MediaPipe world landmarks','fps':30,'summary':summ,'frames':frames},open(out,'w'))
print(json.dumps(summ,indent=1)[:3000]); print('frames',len(frames),'with hands',sum(1 for f in frames if f['hands']))
