# python room_build/char_tripo_sheets.py <shots dir> <out dir> : body and face comparison sheets (reference next to render).
from PIL import Image, ImageDraw
import numpy as np, sys
q=sys.argv[1]+'/'; R=__import__('os').path.join(__import__('os').path.dirname(__file__),'..','docs/design/char-tripo/refs')+'/'; out=sys.argv[2]
def lab(im,t):
    d=ImageDraw.Draw(im); d.rectangle([0,0,len(t)*6+10,16],fill=(0,0,0)); d.text((5,3),t,fill=(255,255,255)); return im
def headcrop(f):
    im=Image.open(f).convert('RGB'); a=np.asarray(im).sum(2)>60; ys,xs=np.nonzero(a)
    top=ys.min(); h=int((ys.max()-top)*0.15); cx=int(xs[ys<top+h].mean())
    return im.crop((cx-int(h*0.75), top-h//8, cx+int(h*0.75), top-h//8+int(h*1.5))).resize((700,700))
rows=[('face_front','face_front.png',None),('face_3q_a','face_3q_a.png',None),('face_3q_b','face_3q_b.png',None),
      ('face_side_left',None,'body_side_left.png'),('face_side_right',None,'body_side_right.png')]
sheet=Image.new('RGB',(1400,700*len(rows)))
for i,(m,ref,body) in enumerate(rows):
    r=Image.open(R+ref).convert('RGB').resize((700,700)) if ref else headcrop(R+body)
    sheet.paste(lab(r,'reference '+(ref or body+' (crop)')),(0,700*i)); sheet.paste(lab(Image.open(q+m+'.png').convert('RGB'),'Tripo '+m),(700,700*i))
sheet.save(out+'/face_compare.jpg',quality=88)
ims=[lab(Image.open(q+n+'.png').convert('RGB'),'Tripo '+n) for n in ['body_front','body_left','body_back','body_right']]
refs=[Image.open(R+f).convert('RGB').crop((474,0,1574,1964)).resize((560,1000)) for f in ['body_front.png','body_side_left.png','body_back.png','body_side_right.png']]
s=Image.new('RGB',(2240,2000)); [s.paste(lab(r,'reference'),(i*560,0)) for i,r in enumerate(refs)]; [s.paste(im,(i*560,1000)) for i,im in enumerate(ims)]
s.save(out+'/body_compare.jpg',quality=88)
