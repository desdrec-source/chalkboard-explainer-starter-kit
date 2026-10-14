"""Procedurally drawn RGBA sprite: hand + short forearm with dark sleeve cuff, holding chalk.
build() -> (PIL RGBA image, (tip_x, tip_y) in sprite px, forearm angle in degrees).
No external image assets are used."""
import numpy as np, math
from PIL import Image, ImageDraw, ImageFilter
from scipy.ndimage import distance_transform_edt, gaussian_filter
rng=np.random.default_rng(3)
SS=3                 # supersample for hand detail
OX,OY=60,420         # local origin (chalk tip) inside sprite canvas (1x px)
CW,CH=2900,1700      # sprite canvas 1x
ARM_ANG=22           # forearm direction relative to chalk axis (deg, +down)

SKIN=np.array([226,176,140],np.float32)
SKIN_D=np.array([170,112,82],np.float32)
SKIN_L=np.array([246,212,182],np.float32)

def shade_layer(mask,base,dark,light,rad,ss,lightdir=(-0.5,-0.8),outline=True):
    """cylindrical-ish shading from mask (float 0..1)"""
    m=(mask>0.5)
    dist=distance_transform_edt(m).astype(np.float32)
    t=np.clip(dist/(rad*ss),0,1)**0.6
    col=dark[None,None,:]*(1-t[...,None])+base[None,None,:]*t[...,None]
    # directional highlight: shift of mask
    gy,gx=np.gradient(gaussian_filter(dist,2*ss))
    nrm=np.sqrt(gx**2+gy**2)+1e-6
    lam=np.clip(-(gx*lightdir[0]+gy*lightdir[1])/nrm,0,1)*np.clip(1-t*1.2,0,1)*0.0
    hl=np.clip(gaussian_filter(m.astype(np.float32),rad*ss*0.6)-0.55,0,1)*1.6
    col=col*(1-hl[...,None]*0.35)+light[None,None,:]*(hl[...,None]*0.35)
    col=col*(1+ (rng.random(m.shape)[...,None]-0.5)*0.04)
    a=gaussian_filter(m.astype(np.float32),0.6*ss)
    if outline:
        edge=np.clip(1-dist/(1.6*ss),0,1)*m
        col=col*(1-edge[...,None]*0.35)
    return np.dstack([np.clip(col,0,255),a*255])

def over(dst,src):
    sa=src[...,3:4]/255; da=dst[...,3:4]/255
    oa=sa+da*(1-sa)
    oc=(src[...,:3]*sa+dst[...,:3]*da*(1-sa))/np.maximum(oa,1e-6)
    return np.dstack([oc,oa*255])

def poly_mask(shape,pts,ss):
    im=Image.new('L',(shape[1],shape[0]),0); ImageDraw.Draw(im).polygon([(x*ss,y*ss) for x,y in pts],fill=255)
    return np.asarray(im,np.float32)/255

def capsule(shape,p0,p1,r0,r1,ss,n=24):
    """tapered capsule as polygon"""
    p0=np.array(p0,float);p1=np.array(p1,float); d=p1-p0; L=np.linalg.norm(d); u=d/L; v=np.array([-u[1],u[0]])
    pts=[]
    for a in np.linspace(math.pi/2,3*math.pi/2,n): pts.append(p0+r0*(math.cos(a)*u+math.sin(a)*v)*1)
    for a in np.linspace(-math.pi/2,math.pi/2,n): pts.append(p1+r1*(math.cos(a)*u+math.sin(a)*v))
    return poly_mask(shape,[tuple(p) for p in pts],ss)

def smooth_poly(pts,n=10):
    P=np.array(pts,float); P=np.vstack([P[-1],P,P[0],P[1]]); out=[]
    for i in range(1,len(P)-2):
        p0,p1,p2,p3=P[i-1],P[i],P[i+1],P[i+2]
        for t in np.linspace(0,1,n,endpoint=False):
            out.append(0.5*((2*p1)+(-p0+p2)*t+(2*p0-5*p1+4*p2-p3)*t*t+(-p0+3*p1-3*p2+p3)*t**3))
    return [tuple(p) for p in out]

def build():
    # ---- detailed hand region in local coords x:-30..470, y:-170..230 ----
    X0,Y0,HW,HH=-30,-170,520,420
    sh=(HH*SS,HW*SS)
    L=lambda pts:[(x-X0,y-Y0) for x,y in pts]
    lay=np.zeros(sh+(4,),np.float32)
    ca,sa=math.cos(math.radians(ARM_ANG)),math.sin(math.radians(ARM_ANG))
    # wrist/forearm start (in hand region)
    def arm_pt(s,off): return (300+s*ca-off*sa, 20+s*sa+off*ca)
    forearm=[arm_pt(0,-78),arm_pt(400,-92),arm_pt(400,88),arm_pt(0,74)]
    # back of hand
    back=smooth_poly([(118,-78),(170,-104),(250,-98),(318,-70),(345,-10),(330,60),(280,96),(205,104),(150,92),(120,60),(108,10)],8)
    lay=over(lay,shade_layer(poly_mask(sh,L(back),SS),SKIN,SKIN_D,SKIN_L,45,SS))
    # tendon / knuckle hints
    hint=Image.new('L',(sh[1],sh[0]),0); d=ImageDraw.Draw(hint)
    for (x0,y0,x1,y1) in [(150,-50,290,-40),(150,-5,295,5),(155,40,285,45)]:
        d.line([((x0-X0)*SS,(y0-Y0)*SS),((x1-X0)*SS,(y1-Y0)*SS)],fill=255,width=5*SS)
    hm=gaussian_filter(np.asarray(hint,np.float32)/255,4*SS)*poly_mask(sh,L(back),SS)
    lay[...,:3]=lay[...,:3]*(1-hm[...,None]*0.12)+SKIN_L*(hm[...,None]*0.12)
    for (kx,ky) in [(140,-62),(128,-12),(132,36),(148,72)]:
        kb=np.zeros(sh,np.float32); yy,xx=np.mgrid[0:sh[0],0:sh[1]]
        kb=np.exp(-(((xx-(kx-X0)*SS)**2+(yy-(ky-Y0)*SS)**2)/(2*(11*SS)**2)))*poly_mask(sh,L(back),SS)
        lay[...,:3]=lay[...,:3]*(1-kb[...,None]*0.3)+SKIN_L*(kb[...,None]*0.3)
    # pinky + ring finger (curled, below chalk)
    pinky=capsule(sh,L([(150,82)])[0],L([(110,96)])[0],22,17,SS)
    lay=over(lay,shade_layer(pinky,SKIN,SKIN_D,SKIN_L,12,SS))
    ringf=capsule(sh,L([(130,46)])[0],L([(80,66)])[0],25,19,SS)
    lay=over(lay,shade_layer(ringf,SKIN,SKIN_D,SKIN_L,13,SS))
    # gold ring on ring finger
    fu=np.array([-50.,20.]);fu/=np.linalg.norm(fu); fv=np.array([-fu[1],fu[0]]); c=np.array([110.,54.])
    band=capsule(sh,L([tuple(c-fv*32)])[0],L([tuple(c+fv*32)])[0],4.5,4.5,SS)
    from scipy.ndimage import binary_dilation
    rg=band*binary_dilation(ringf>0.5,iterations=2*SS)
    gold=shade_layer(rg,np.array([222,182,70],np.float32),np.array([150,105,30],np.float32),np.array([255,240,170],np.float32),3,SS,outline=False)
    lay=over(lay,gold)
    # middle finger curled under chalk
    mid=capsule(sh,L([(128,6)])[0],L([(58,30)])[0],26,20,SS)
    lay=over(lay,shade_layer(mid,SKIN,SKIN_D,SKIN_L,14,SS))
    # chalk stick along +x from tip (0,0), slight taper at tip
    chalk=[(0,-6),(6,-10),(14,-11),(150,-11),(150,11),(14,11),(6,10),(0,6),(-2,0)]
    cm=poly_mask(sh,L(chalk),SS)
    ch=shade_layer(cm,np.array([246,246,240],np.float32),np.array([196,196,190],np.float32),np.array([255,255,255],np.float32),7,SS,outline=True)
    ch[...,:3]*=1+(rng.random(sh)[...,None]-0.5)*0.08
    # chalk dust smudge near tip
    lay=over(lay,ch)
    # index finger over chalk (from knuckle to tip near chalk)
    idx=capsule(sh,L([(140,-50)])[0],L([(40,-8)])[0],26,18,SS)
    lay=over(lay,shade_layer(idx,SKIN,SKIN_D,SKIN_L,14,SS))
    # index fingertip crease + nail
    nail=capsule(sh,L([(58,-16)])[0],L([(38,-7)])[0],9,9,SS)
    lay=over(lay,shade_layer(nail,np.array([240,200,188],np.float32),np.array([205,150,140],np.float32),np.array([255,236,228],np.float32),5,SS))
    # thumb along upper side
    th=capsule(sh,L([(235,-80)])[0],L([(62,-34)])[0],34,19,SS)
    lay=over(lay,shade_layer(th,SKIN,SKIN_D,SKIN_L,16,SS))
    tnail=capsule(sh,L([(84,-44)])[0],L([(64,-38)])[0],10,9,SS)
    lay=over(lay,shade_layer(tnail,np.array([240,200,188],np.float32),np.array([205,150,140],np.float32),np.array([255,236,228],np.float32),5,SS))
    # middle finger nail peeking below chalk
    mnail=capsule(sh,L([(70,26)])[0],L([(56,31)])[0],8,8,SS)
    lay=over(lay,shade_layer(mnail,np.array([240,200,188],np.float32),np.array([205,150,140],np.float32),np.array([255,236,228],np.float32),4,SS))
    # finger creases
    cr=Image.new('L',(sh[1],sh[0]),0); d=ImageDraw.Draw(cr)
    for (x0,y0,x1,y1) in [(95,-38,90,-18),(92,22,86,40),(100,56,97,72),(160,-70,170,-58)]:
        d.line([((x0-X0)*SS,(y0-Y0)*SS),((x1-X0)*SS,(y1-Y0)*SS)],fill=255,width=2*SS)
    cr=gaussian_filter(np.asarray(cr,np.float32)/255,1.2*SS)
    lay[...,:3]*=(1-cr[...,None]*0.3)
    hand=Image.fromarray(np.clip(lay,0,255).astype(np.uint8),'RGBA').resize((HW,HH),Image.LANCZOS)

    # ---- long forearm on big canvas ----
    big=np.zeros((CH,CW,4),np.float32)
    def ap(s,off):
        x,y=arm_pt(s,off); return (x+OX,y+OY)
    ARM_L=260
    arm=[ap(0,-78),ap(ARM_L,-90),ap(ARM_L,86),ap(0,74)]
    m=poly_mask((CH,CW),arm,1)
    big=over(big,shade_layer(m,SKIN,SKIN_D,SKIN_L,48,1))
    # hair tie on wrist
    tie=[ap(62,-95),ap(76,-97),ap(78,95),ap(64,93)]
    from scipy.ndimage import binary_dilation
    tm=poly_mask((CH,CW),smooth_poly(tie,6),1)*binary_dilation(m>0.5,iterations=3)
    tie_l=shade_layer(tm,np.array([30,30,34],np.float32),np.array([8,8,10],np.float32),np.array([95,95,105],np.float32),5,1,outline=False)
    # dark sleeve with cuff
    sl=[ap(215,-104),ap(232,-108),ap(470,-122),ap(470,120),ap(232,104),ap(215,100)]
    sm=gaussian_filter(poly_mask((CH,CW),sl,1),1.0)
    sleeve=shade_layer(sm,np.array([52,60,84],np.float32),np.array([22,26,40],np.float32),np.array([90,100,130],np.float32),40,1)
    # cuff seam + folds
    yy,xx=np.mgrid[0:CH,0:CW].astype(np.float32)
    sax=(xx-OX-300)*ca+(yy-OY-20)*sa
    seam=np.exp(-((sax-245)/3.0)**2)*sm
    folds=(0.5+0.5*np.sin(sax*0.09+((xx-OX)*-sa+(yy-OY)*ca)*0.02))*np.clip((sax-260)/60,0,1)*sm
    sleeve[...,:3]*=(1-0.35*seam[...,None])*(1-0.12*folds[...,None])
    big=over(big,sleeve)
    # fade out the far end so only a short forearm/sleeve is visible
    fade=np.clip(1-(sax-330)/110,0,1)
    big[...,3]*=fade
    bi=Image.fromarray(np.clip(big,0,255).astype(np.uint8),'RGBA')
    bi.alpha_composite(hand,(X0+OX,Y0+OY))
    bi.alpha_composite(Image.fromarray(np.clip(tie_l,0,255).astype(np.uint8),'RGBA'))
    return bi,(OX,OY),ARM_ANG

if __name__=='__main__':
    # preview: python -m chalkkit.hand_sprite [out.png]
    import sys
    im,tip,_=build()
    prev=Image.new('RGBA',(900,700),(47,79,58,255)); prev.alpha_composite(im.crop((0,200,900,900)))
    prev.save(sys.argv[1] if len(sys.argv)>1 else 'hand_preview.png'); print('chalk tip at',tip)
