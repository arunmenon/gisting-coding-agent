from PIL import Image, ImageDraw, ImageFont
import math, os
D = "/private/tmp/claude-501/-Users-arunmenon-projects-gisting/82deba89-c9a1-41e0-9e61-ec090b34e902/scratchpad/paper_figs"
S = 2  # supersample for crisp downscaled output

INK=(31,36,48); INK2=(96,102,112); WHITE=(255,255,255); PAPER=(255,255,255)
SLATE=(69,96,122); SLATE_F=(232,237,242)
PLUM=(107,63,115); PLUM_F=(240,232,243)
PETROL=(31,95,110); PETROL_F=(224,238,240)
COPPER=(176,98,45); COPPER_F=(247,236,227)
NEUT=(200,205,212); NEUT_F=(244,245,247)
GOLD=(150,120,30)

def font(sz, b=False):
    p = "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if b else "/System/Library/Fonts/Supplemental/Arial.ttf"
    try: return ImageFont.truetype(p, sz*S)
    except: return ImageFont.load_default()

def canvas(w,h):
    im=Image.new("RGB",(w*S,h*S),PAPER); return im, ImageDraw.Draw(im)

def rbox(d,x,y,w,h,text,accent=NEUT,fill=NEUT_F,tsz=15,bold=True,r=14,shadow=True,tcol=None):
    x,y,w,h,r=x*S,y*S,w*S,h*S,r*S
    if shadow:
        d.rounded_rectangle([x+3*S,y+4*S,x+w+3*S,y+h+4*S],radius=r,fill=(0,0,0,0) if False else (238,239,241))
    d.rounded_rectangle([x,y,x+w,y+h],radius=r,fill=fill,outline=accent,width=3*S)
    f=font(tsz,bold); ls=text.split("\n"); lh=tsz*S*1.28
    ty=y+h/2-lh*len(ls)/2+lh*0.12
    for i,l in enumerate(ls):
        w_=d.textlength(l,font=f); d.text((x+w/2-w_/2,ty+i*lh),l,fill=tcol or INK,font=f)

def chip(d,cx,cy,txt,accent,tsz=13):
    f=font(tsz,True); tw=d.textlength(txt,font=f); pad=10*S
    x0,y0=cx*S-tw/2-pad,cy*S-tsz*S*0.75-4*S; x1,y1=cx*S+tw/2+pad,cy*S+tsz*S*0.75+4*S
    d.rounded_rectangle([x0,y0,x1,y1],radius=(y1-y0)/2,fill=accent)
    d.text((cx*S-tw/2,cy*S-tsz*S*0.62),txt,fill=WHITE,font=f)

def arrow(d,x1,y1,x2,y2,col=INK,w=3,label=None,lsz=13,dash=False):
    x1,y1,x2,y2=x1*S,y1*S,x2*S,y2*S
    if dash:
        # simple dashed
        n=int(math.hypot(x2-x1,y2-y1)/(10*S));
        for i in range(n):
            if i%2==0:
                a=i/n; b=(i+1)/n; d.line([x1+(x2-x1)*a,y1+(y2-y1)*a,x1+(x2-x1)*b,y1+(y2-y1)*b],fill=col,width=w*S)
    else:
        d.line([x1,y1,x2,y2],fill=col,width=w*S)
    ang=math.atan2(y2-y1,x2-x1); L=13*S
    d.polygon([(x2,y2),(x2-L*math.cos(ang-0.42),y2-L*math.sin(ang-0.42)),(x2-L*math.cos(ang+0.42),y2-L*math.sin(ang+0.42))],fill=col)
    if label:
        f=font(lsz); mx,my=(x1+x2)/2,(y1+y2)/2; tw=d.textlength(label,font=f)
        d.rectangle([mx-tw/2-4*S,my-lsz*S-2*S,mx+tw/2+4*S,my-2*S],fill=WHITE)
        d.text((mx-tw/2,my-lsz*S),label,fill=INK2,font=f)

def band(d,x,y,w,h,title,tint,accent,r=16):
    x,y,w,h,r=x*S,y*S,w*S,h*S,r*S
    d.rounded_rectangle([x,y,x+w,y+h],radius=r,fill=tint)
    f=font(13,True); d.text((x+16*S,y+10*S),title,fill=accent,font=f)

def text(d,x,y,s,col=INK,sz=14,b=False):
    d.text((x*S,y*S),s,fill=col,font=font(sz,b))

def save(im,name):
    im=im.resize((im.width//S,im.height//S),Image.LANCZOS); im.save(D+"/"+name);

# ---------------- FIG 1 SYSTEM ----------------
im,d=canvas(1500,470)
text(d,40,34,"Measurement and serving path",sz=20,b=True)
rbox(d,40,90,250,96,"Claude Code\nunmodified client",NEUT,NEUT_F,tsz=15)
arrow(d,292,138,392,138,label="Messages API")
rbox(d,396,90,230,96,"logging proxy\n(tap)",PETROL,PETROL_F,tsz=15,tcol=PETROL)
arrow(d,628,138,728,138,label="forward")
rbox(d,732,90,430,96,"vLLM 0.28  (no engine patch)\nQwen3.8-27B  .  one 96 GB GPU",SLATE,SLATE_F,tsz=14)
arrow(d,540,188,540,250,col=PETROL,label="log request, reply, timing")
rbox(d,396,254,230,66,"session log",PETROL,PETROL_F,tsz=14,tcol=PETROL)
# composition bar
text(d,40,344,"Composition of one request  (schematic; segment widths not to token scale)",sz=15,b=True)
bx,by,bh=40,384,54
segs=[("tool schemas",700,PLUM,WHITE),("rules",95,COPPER,WHITE),("conversation so far",470,NEUT_F,INK)]
x=bx
for lab,w,col,tc in segs:
    d.rounded_rectangle([x*S,by*S,(x+w)*S,(by+bh)*S],radius=6*S,fill=col,outline=NEUT if col==NEUT_F else col,width=2*S)
    f=font(13,True); d.text((x*S+10*S,by*S+bh*S/2-8*S),lab,fill=tc,font=f); x+=w
chip(d,150,300+ (by-300)+90, "static, gistable", PLUM) if False else None
text(d,40,452,"Schematic. Plum and copper are the static span (byte-identical across sessions); the outlined block changes each turn. The dynamic system fields (cwd, date, id) are omitted here for clarity.",col=INK2,sz=12)
save(im,"fig1_system.png")

# ---------------- FIG 2 METHOD ----------------
im,d=canvas(1500,640)
band(d,30,26,1440,150,"A .  GROW THE EMBEDDING TABLE",SLATE_F,SLATE)
rbox(d,60,74,720,74,"248,077 real-token rows  (frozen, unchanged)",NEUT,WHITE,tsz=15)
rbox(d,800,74,220,74,"+ N gist rows",PLUM,PLUM_F,tsz=15,tcol=PLUM)
text(d,1044,90,"each gist row =",col=INK2,sz=13); text(d,1044,110,"mean of the k span",col=INK2,sz=13); text(d,1044,130,"tokens it replaces",col=INK2,sz=13)
band(d,30,196,1440,220,"B .  SELF-DISTILLATION   (all weights frozen; only the N gist rows are trained)",PETROL_F,PETROL)
rbox(d,60,250,430,72,"TEACHER: reads the full 17.5k-token span",SLATE,SLATE,tsz=14,tcol=WHITE)
rbox(d,60,344,430,60,"STUDENT: reads N gist rows instead",PLUM,PLUM_F,tsz=14,tcol=PLUM)
arrow(d,494,286,650,320); arrow(d,494,374,650,336)
rbox(d,654,300,210,72,"KL at each\nresponse token",NEUT,WHITE,tsz=14)
arrow(d,868,336,1010,336)
rbox(d,1014,300,420,72,"gradient updates the gist rows only\n(11M at 8:1; 22M at 4:1, of 27B)",PLUM,PLUM_F,tsz=13,tcol=PLUM)
band(d,30,436,1440,170,"C .  SERVE   (no change to client or engine source)",COPPER_F,COPPER)
rbox(d,60,486,400,70,"proxy swaps the span\nfor gist tokens",PETROL,PETROL,tsz=14,tcol=WHITE)
arrow(d,462,521,560,521)
rbox(d,564,486,470,70,"conditional template omits the\ntool block; mask blocks gist ids",NEUT,WHITE,tsz=14)
arrow(d,1036,521,1134,521)
rbox(d,1138,486,300,70,"engine serves it as\nan ordinary model",SLATE,SLATE_F,tsz=14)
save(im,"fig2_method.png")

# ---------------- FIG 3 CACHE ----------------
im,d=canvas(1500,470)
band(d,30,26,1440,180,"WITHOUT A CACHE  .  every training step recomputes the teacher",NEUT_F,INK2)
rbox(d,60,74,330,60,"teacher pass (full 17.5k prompt)",SLATE,SLATE,tsz=13,tcol=WHITE)
rbox(d,60,146,330,60,"student pass (gist)",PLUM,PLUM_F,tsz=13,tcol=PLUM)
arrow(d,394,104,540,130); arrow(d,394,176,540,150)
rbox(d,544,110,150,60,"KL loss",NEUT,WHITE,tsz=14)
arrow(d,698,140,820,140,label="update gist")
text(d,835,120,"the teacher pass is recomputed every step,",col=INK2,sz=13)
text(d,835,140,"though the teacher never changes.",col=INK2,sz=13)
band(d,30,226,1440,214,"WITH A CACHE  .  teacher recorded once, reused for every recipe",PETROL_F,PETROL)
rbox(d,60,272,330,60,"teacher top-32 log-probs (cached once)",PETROL,PETROL,tsz=12,tcol=WHITE)
rbox(d,60,344,330,60,"student pass (gist)",PLUM,PLUM_F,tsz=13,tcol=PLUM)
arrow(d,394,302,540,332); arrow(d,394,374,540,348)
rbox(d,544,308,150,60,"KL loss",NEUT,WHITE,tsz=14)
arrow(d,698,338,820,338,label="update gist")
text(d,835,314,"both the cached teacher and the student feed the loss;",col=INK2,sz=13)
text(d,835,334,"training becomes a student-only pass. Top-32 retains",col=INK2,sz=13)
text(d,835,354,"~0.999 of teacher mass; the target is KL from this",col=INK2,sz=13)
text(d,835,374,"truncated, renormalised teacher (tail not validated).",col=INK2,sz=13)
save(im,"fig3cache.png"); os.replace(D+"/fig3cache.png",D+"/fig4_cache.png")

# ---------------- FIG SPAN ----------------
im,d=canvas(1700,580)
text(d,40,30,"Recovering the static span from logged sessions",sz=19,b=True)
def step(n,x,y,w,h,txt,accent,fill):
    rbox(d,x,y,w,h,txt,accent,fill,tsz=14); chip(d,x+18,y,str(n),accent)
step(1,60,90,250,96,"many served requests\n(logged by the tap)",PETROL,PETROL_F)
arrow(d,312,138,372,138)
step(2,376,90,330,96,"cross-session diff of\nsystem text + tool array",SLATE,SLATE_F)
arrow(d,708,138,768,138)
# segmented bar as step 3
chip(d,790,86,"3",COPPER); text(d,816,80,"one rendered prompt, segmented",sz=14,b=True)
bx,by,bh=790,110,50
segs=[("rules A",120,COPPER,WHITE,True),("cwd/date",95,NEUT_F,INK,False),("rules B",120,COPPER,WHITE,True),("tool schemas",340,PLUM,WHITE,True),("conversation",180,NEUT_F,INK,False)]
x=bx; spans=[]
for lab,w,col,tc,gist in segs:
    d.rounded_rectangle([x*S,by*S,(x+w)*S,(by+bh)*S],radius=5*S,fill=col,outline=NEUT if col==NEUT_F else col,width=2*S)
    d.text((x*S+7*S,by*S+bh*S/2-8*S),lab,fill=tc,font=font(12,True)); spans.append((x,x+w,gist)); x+=w
# gold brackets under the gistable segments only; raw ticks under dynamic ones
by2=by+bh+9
d.line([spans[0][0]*S,by2*S,spans[0][1]*S,by2*S],fill=GOLD,width=3*S)      # rules A
d.line([spans[2][0]*S,by2*S,spans[3][1]*S,by2*S],fill=GOLD,width=3*S)      # rules B + tool schemas
text(d,spans[3][0]-40,by2+6,"static span, gistable",col=GOLD,sz=13,b=True)
for a0,a1,gist in spans:
    if not gist:
        d.line([a0*S,by2*S,a1*S,by2*S],fill=INK2,width=2*S)
text(d,spans[1][0]-6,by2+30,"dynamic, kept raw",col=INK2,sz=11)
# side card per-session
rbox(d,60,250,300,168,"per-session content\nlocalised by the diff:\nworking directory\ngit status / date\nserved model name\n(kept as raw tokens)",NEUT,NEUT_F,tsz=13,bold=False)
# flow down to results
arrow(d,1050,178,1050,246)
step(4,760,250,560,66,"count via engine tokenizer  ->  span = 17,540 tokens",PETROL,PETROL_F)
arrow(d,1050,318,1050,372)
rbox(d,720,376,640,74,"integrated share = static tokens x turns / total input tokens\n(reported per session; Figure 7)",SLATE,SLATE_F,tsz=13)
save(im,"figspan.png"); os.replace(D+"/figspan.png",D+"/fig_span.png")

# ---------------- FIG ARMS ----------------
im,d=canvas(1560,560)
text(d,40,28,"Two-arm evaluation on one served model",sz=19,b=True)
band(d,300,78,700,120,"",SLATE_F,SLATE)
text(d,588,86,"TEACHER ARM",col=SLATE,sz=13,b=True)
band(d,300,300,700,120,"",PLUM_F,PLUM)
text(d,588,308,"STUDENT ARM",col=PLUM,sz=13,b=True)
rbox(d,60,180,220,90,"same task suite\n(run twice)",NEUT,WHITE,tsz=15)
arrow(d,282,205,360,150); arrow(d,282,240,360,352)
rbox(d,360,110,560,74,"full prompt sent as-is",SLATE,SLATE,tsz=15,tcol=WHITE,shadow=False)
rbox(d,360,326,560,74,"tap swaps the span for gist tokens",PLUM,WHITE,tsz=15,tcol=PLUM,shadow=False)
arrow(d,922,147,1060,220); arrow(d,922,363,1060,300)
rbox(d,1064,196,430,120,"ONE served model\nidentical weights\n(gist rows added only)",PETROL,PETROL_F,tsz=15,tcol=PETROL)
arrow(d,1279,318,1279,392)
rbox(d,1064,396,430,84,"same programmatic checker\n->  score",NEUT,WHITE,tsz=15)
text(d,40,512,"Both arms share the weights and the checker, so a gap isolates the span swap from any weight change; single-run gaps may still",col=INK2,sz=13)
text(d,40,532,"come from generation or grader variability. Sub-agent child sessions run unswapped on the full prompt.",col=INK2,sz=13)
save(im,"figarms.png"); os.replace(D+"/figarms.png",D+"/fig_arms.png")

# ---------------- FIG DEFECT ----------------
im,d=canvas(1560,470)
text(d,40,28,"The verbatim-content failure, and its fix",sz=19,b=True)
band(d,30,70,1500,150,"BEFORE  .  the working-directory line (with a session id) was compressed into the gist",PLUM_F,PLUM)
rbox(d,60,118,540,64,"gist:  rules + scratchpad/<UUID>/",PLUM,PLUM,tsz=15,tcol=WHITE,shadow=False)
rbox(d,612,118,150,64,"work/s1",NEUT,WHITE,tsz=14)
arrow(d,766,150,900,150)
text(d,912,124,"Write path  =",sz=14,b=True); text(d,912,150,"/Users/.../Code/gisting/s1/",col=(150,50,45),sz=14); text(d,912,172,"(invented, wrong)",col=(150,50,45),sz=12)
band(d,30,238,1500,150,"AFTER  .  paths, ids, dates, and model name kept raw by pattern",PETROL_F,PETROL)
rbox(d,60,286,220,64,"gist:  rules",PLUM,PLUM,tsz=15,tcol=WHITE,shadow=False)
rbox(d,292,286,470,64,"raw:  cwd, UUID, date, model name",NEUT,WHITE,tsz=14)
arrow(d,766,318,900,318)
text(d,912,292,"Write path  =",sz=14,b=True); text(d,912,318,".../scratchpad/<UUID>/work/s1/",col=PETROL,sz=14); text(d,912,340,"(correct)",col=PETROL,sz=12)
text(d,40,410,"Hard suite at 8:1: 11/16 -> 16/16 (11/15 -> 15/15 excluding one defective delete probe; full prompt 15/15 in both). One rerun, one residual wrong-path event. ~196 session-specific tokens kept raw.",col=INK2,sz=13)
save(im,"figdefect.png"); os.replace(D+"/figdefect.png",D+"/fig5_defect.png")

print("redrawn polished:", [f for f in ("fig1_system","fig2_method","fig4_cache","fig_span","fig_arms","fig5_defect")])

# ================= DATA CHARTS (real numbers) =================
GREY=(150,155,162)
def hbaseline(d,x0,y0,w,h):
    d.line([x0*S,y0*S,x0*S,(y0+h)*S],fill=INK2,width=2*S)
    d.line([x0*S,(y0+h)*S,(x0+w)*S,(y0+h)*S],fill=INK2,width=2*S)
def dline(d,x0,x1,yy,col):
    n=int((x1-x0)/12)
    for i in range(n):
        if i%2==0:
            xa=x0+i*12; xb=x0+(i+1)*12
            d.line([xa*S,yy*S,xb*S,yy*S],fill=col,width=2*S)
def panel(d,x0,y0,w,h,title,sub,glabels,series,ymax,fmt):
    text(d,x0,y0-32,title,sz=15,b=True)
    base=y0+h; hbaseline(d,x0,y0,w,h)
    ng=len(glabels); nb=len(series); gw=w/ng; bw=gw*0.60/nb
    for gi,gl in enumerate(glabels):
        gx=x0+gi*gw+gw*0.20
        for si,(name,col,vals) in enumerate(series):
            v=vals[gi]; bh=(v/ymax)*h; bxx=gx+si*bw
            d.rectangle([bxx*S,(base-bh)*S,(bxx+bw)*S,base*S],fill=col)
            lbl=fmt(v); f=font(11,True); tw=d.textlength(lbl,font=f)
            d.text(((bxx+bw/2)*S-tw/2,(base-bh-17)*S),lbl,fill=INK,font=f)
        f=font(12,True); tw=d.textlength(gl,font=f)
        d.text((((x0+gi*gw+gw/2)*S)-tw/2,(base+8)*S),gl,fill=INK,font=f)
    text(d,x0,base+30,sub,col=INK2,sz=11)
def swatch(d,x,y,col,lab):
    d.rectangle([x*S,y*S,(x+22)*S,(y+16)*S],fill=col)
    d.text(((x+30)*S,(y+1)*S),lab,fill=INK,font=font(13,True))

# ---------------- FIG 6 SHARE (8 real sessions) ----------------
im,d=canvas(1340,520)
text(d,40,30,"Integrated static-span share per session",sz=19,b=True)
text(d,40,58,"Eight logged sessions, full catalogue (static span 21,109 tokens). Share = static tokens x turns / total input tokens.",col=INK2,sz=13)
shares=[0.75,0.73,0.73,0.72,0.69,0.73,0.71,0.72]
labels=["S0","S1","S2","S3","S4","S5","S6","S7"]
x0,y0,w,h=90,130,1000,300; ymax=0.85; base=y0+h
hbaseline(d,x0,y0,w,h)
# gate + mean lines, labels in the right margin (clear of bars)
gate_y=base-(0.25/ymax)*h; mean_y=base-(0.72/ymax)*h
dline(d,x0,x0+w,gate_y,COPPER); text(d,x0+w+10,gate_y-8,"0.25 gate",col=COPPER,sz=12,b=True)
dline(d,x0,x0+w,mean_y,PLUM); text(d,x0+w+10,mean_y-8,"mean 0.72",col=PLUM,sz=12,b=True)
gw=w/len(shares); bw=gw*0.5
for i,(v,lab) in enumerate(zip(shares,labels)):
    bx=x0+i*gw+gw*0.25; bh=(v/ymax)*h
    d.rectangle([bx*S,(base-bh)*S,(bx+bw)*S,base*S],fill=SLATE)
    f=font(12,True); s=("%.2f"%v); tw=d.textlength(s,font=f)
    d.text(((bx+bw/2)*S-tw/2,(base-bh-18)*S),s,fill=INK,font=f)
    tw=d.textlength(lab,font=font(12,True)); d.text(((bx+bw/2)*S-tw/2,(base+8)*S),lab,fill=INK,font=font(12,True))
text(d,x0,base+34,"Every session clears the 0.25 screening heuristic (not an economic break-even). Median 0.73; share falls within longer sessions as context grows.",col=INK2,sz=12)
save(im,"figshare.png"); os.replace(D+"/figshare.png",D+"/fig3_share.png")

# ---------------- FIG 8 LATENCY (3 panels incl. E2E) ----------------
im,d=canvas(1680,540)
text(d,40,30,"Serving on one fixed-output-length replay",sz=19,b=True)
swatch(d,40,64,GREY,"full prompt"); swatch(d,200,64,PLUM,"gist")
text(d,320,65,"72 requests per arm at each concurrency; prefix caching on in both arms; one replay.",col=INK2,sz=12)
gl=["c=1","c=4","c=8"]
def f1(v): return "%.1f"%v
panel(d,90,170,420,260,"Throughput (req/min)","higher is better",gl,
      [("full",GREY,[6.87,16.42,20.02]),("gist",PLUM,[7.19,18.90,23.18])],26,f1)
panel(d,640,170,420,260,"Median end-to-end latency (s)","lower is better",gl,
      [("full",GREY,[8.23,12.96,14.95]),("gist",PLUM,[7.97,11.47,13.14])],17,f1)
panel(d,1190,170,420,260,"p90 time-to-first-token (s)","lower is better",gl,
      [("full",GREY,[2.69,8.96,12.72]),("gist",PLUM,[2.37,5.46,11.52])],15,f1)
save(im,"figlatency.png"); os.replace(D+"/figlatency.png",D+"/fig6_latency.png")
print("redrew data charts: fig3_share, fig6_latency")

# ---------------- FIG LOOP (the lab) ----------------
im,d=canvas(1820,470)
text(d,40,28,"The automated experiment loop (the lab)",sz=19,b=True)
text(d,40,54,"One detached controller drives every recipe end to end; each recipe gets a fresh GPU that is torn down when it finishes.",col=INK2,sz=13)
py=112; ph=112
rbox(d,40,py,150,ph,"recipe\nqueue\n(rows)",NEUT,WHITE,tsz=13)
arrow(d,192,py+ph/2,214,py+ph/2)
rbox(d,216,py,236,ph,"provision fresh GPU\ncopy code, data,\nteacher cache",PETROL,PETROL_F,tsz=13,tcol=PETROL)
arrow(d,454,py+ph/2,476,py+ph/2)
gx,gw=478,556
rbox(d,gx,py,gw,ph,"",SLATE,SLATE_F)
text(d,gx+20,py+12,"chained job on the GPU  .  supervisor restarts on death",col=SLATE,sz=12,b=True)
steps=[("grow",96),("train 1 epoch",140),("serve",80),("write READY",120)]
sx=gx+20; sy=py+48
for i,(lab,w) in enumerate(steps):
    rbox(d,sx,sy,w,50,lab,SLATE,SLATE,tsz=12,tcol=WHITE,shadow=False,r=9)
    if i<len(steps)-1: arrow(d,sx+w+1,sy+25,sx+w+15,sy+25,w=2)
    sx+=w+16
arrow(d,gx+gw+2,py+ph/2,gx+gw+24,py+ph/2)
rbox(d,gx+gw+26,py,300,ph,"controller polls STATE (SSH);\non READY: tunnel + tap,\neval, score, verify swap",PETROL,PETROL_F,tsz=12,tcol=PETROL)
x5=gx+gw+26+300
arrow(d,x5+2,py+ph/2,x5+24,py+ph/2)
rbox(d,x5+26,py,210,ph,"sync artifacts;\nappend results line",PETROL,PETROL_F,tsz=13,tcol=PETROL)
x6=x5+26+210
arrow(d,x6+2,py+ph/2,x6+24,py+ph/2)
rbox(d,x6+26,py,150,ph,"destroy\ninstance",PLUM,PLUM_F,tsz=13,tcol=PLUM)
# loop-back arrow
lb_x=x6+26+75; qx=115
d.line([lb_x*S,(py+ph)*S,lb_x*S,(py+ph+40)*S],fill=INK2,width=3*S)
d.line([lb_x*S,(py+ph+40)*S,qx*S,(py+ph+40)*S],fill=INK2,width=3*S)
arrow(d,qx,py+ph+40,qx,py+ph+2,col=INK2)
tw=d.textlength("next recipe",font=font(13,True)); d.text(((lb_x+qx)/2*S-tw/2,(py+ph+20)*S),"next recipe",fill=INK2,font=font(13,True))
# spend-safety band
sb=py+ph+72
band(d,40,sb,1740,116,"SPEND-SAFETY  .  structural, not vigilance-dependent",COPPER_F,COPPER)
items=[("idle watchdog\nauto-stops the box",380),("ledger records the\ninstance at creation",380),("results synced\nbefore any destroy",380),("global deadline\ntears the sweep down",400)]
ix=70; iy=sb+42
for lab,w in items:
    rbox(d,ix,iy,w,58,lab,COPPER,WHITE,tsz=12,shadow=False); ix+=w+30
# idempotency note below the band
text(d,40,sb+128,"Idempotent per instance via state files: a dropped SSH connection resumes the run, it does not repeat it.",col=INK2,sz=12)
save(im,"figloop.png"); os.replace(D+"/figloop.png",D+"/fig_loop.png")
print("drew fig_loop v2")

# ---------------- FIG 9 SERVING (J10 benchmark: curve + open-loop SLO) ----------------
def linepanel(d,x0,y0,w,h,title,xs,series,ymax,xlabels,ylab,note=None,hlines=()):
    text(d,x0,y0-34,title,sz=15,b=True)
    base=y0+h; hbaseline(d,x0,y0,w,h)
    n=len(xs); step=w/(n-1) if n>1 else w
    def X(i): return x0+i*step
    def Y(v): return base-(min(v,ymax)/ymax)*h
    for k,(yv,col,lab) in enumerate(hlines):
        dline(d,x0,x0+w,Y(yv),col); text(d,x0+w-160,Y(yv)-20 if k==0 else Y(yv)+6,lab,col=col,sz=11,b=True)
    for name,col,vals,dash in series:
        pts=[(X(i)*S,Y(v)*S) for i,v in enumerate(vals)]
        if dash:
            for i in range(len(pts)-1):
                x1,y1=pts[i]; x2,y2=pts[i+1]; segs=8
                for k in range(0,segs,2):
                    a=k/segs; b=(k+1)/segs; d.line([x1+(x2-x1)*a,y1+(y2-y1)*a,x1+(x2-x1)*b,y1+(y2-y1)*b],fill=col,width=3*S)
        else: d.line(pts,fill=col,width=4*S)
        for (px,py),v in zip(pts,vals):
            r=5*S; d.ellipse([px-r,py-r,px+r,py+r],fill=col)
            if v>ymax: d.text((px-10*S,py-22*S),"^",fill=col,font=font(12,True))
    for i,l in enumerate(xlabels):
        f=font(12,True); tw=d.textlength(l,font=f); d.text((X(i)*S-tw/2,(base+8)*S),l,fill=INK,font=f)
    for yv in range(0,int(ymax)+1,int(ymax/5)):
        d.text(((x0-34)*S,(Y(yv)-7)*S),str(yv),fill=INK2,font=font(11))
    text(d,x0,base+30,ylab,col=INK2,sz=11)
    if note: text(d,x0,y0-12,note,col=INK2,sz=11)
    # legend
    lx=x0+8; ly=y0+8
    for name,col,_,_ in series:
        d.line([lx*S,(ly+7)*S,(lx+24)*S,(ly+7)*S],fill=col,width=4*S); d.text(((lx+30)*S,ly*S),name,fill=INK,font=font(12,True)); lx+=30+int(d.textlength(name,font=font(12,True))/S)+22
im,d=canvas(1700,600)
text(d,40,28,"Serving benchmark on a tuned server (H100 NVL 95 GB), full prompt vs gist",sz=19,b=True)
text(d,40,56,"Same server configuration for both arms; 198 turn-ordered requests per arm; fixed 200-token outputs. Left: 3 repeats (spread within marker size). Right: 2 repeats.",col=INK2,sz=12)
cs=["1","2","4","8","16","32","48","64"]
linepanel(d,110,140,640,300,"Closed loop: throughput vs concurrent sessions (requests / min)",cs,
  [("full prompt",GREY,[13.1,22.7,36.9,34.7,42.7,42.7,32.0,29.3],False),("gist 8:1",PLUM,[14.7,25.3,42.7,48.0,59.3,61.3,52.7,41.3],False),("gist 16:1",PETROL,[14.0,24.0,40.0,42.7,53.3,54.0,44.0,36.7],True)],
  70,cs,"concurrent sessions  |  full prompt collapses beyond 32 (KV cache 100%); gist 8:1 peaks at 32, +44%")
ol=["9","18","27","36","54","72"]
linepanel(d,960,140,640,300,"Open loop: p95 end-to-end latency vs offered load (seconds)",ol,
  [("full prompt",GREY,[7.3,8.4,8.7,10.4,23.4,79.5],False),("gist 8:1",PLUM,[5.0,6.7,6.7,7.7,16.6,26.5],False)],
  30,ol,"offered requests / min (Poisson arrivals)  |  within the 2x SLO: full up to ~18, gist up to ~36",
  hlines=[(8.5,GREY,"SLO full 8.5s"),(8.0,PLUM,"SLO gist 8.0s")])
text(d,40,548,"Capacity depends on hardware headroom: on an H200 NVL (143 GB, same config) the peak gain was -2% at normal load and appeared only under pressure (3.1x at 128 sessions). Throughput per $/h: H100 full 16.2, H100 gist 23.2, H200 full 22.5.",col=INK2,sz=12)
save(im,"fig7serving.png"); os.replace(D+"/fig7serving.png",D+"/fig7_serving.png")
print("drew fig7_serving")
