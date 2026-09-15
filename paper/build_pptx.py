from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE
from pptx.chart.data import CategoryChartData
from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION
from PIL import Image
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent

FIG = str(HERE / "paper_figs")
OUT = str(HERE.parent / "Gisting-CTO-deck.pptx")

BG=RGBColor(0x0e,0x14,0x17); BG2=RGBColor(0x14,0x1d,0x21); INK=RGBColor(0xee,0xf3,0xf3)
INK2=RGBColor(0x9f,0xb2,0xb6); LINE=RGBColor(0x25,0x33,0x3a); PETROL=RGBColor(0x3f,0xb0,0xc6)
PETROL2=RGBColor(0x1f,0x5f,0x6e); PLUM=RGBColor(0xc3,0x9b,0xe0); COPPER=RGBColor(0xe0,0x8a,0x4c)
GOOD=RGBColor(0x57,0xc0,0x8a); WARN=RGBColor(0xe3,0xb2,0x4c); SLATE=RGBColor(0x4a,0x5a,0x60); WHITE=RGBColor(0xff,0xff,0xff)
HEAD="Georgia"; BODY="Calibri"; MONO="Consolas"

prs=Presentation(); prs.slide_width=Inches(13.333); prs.slide_height=Inches(7.5)
BLANK=prs.slide_layouts[6]
SW,SH=13.333,7.5

def slide():
    s=prs.slides.add_slide(BLANK)
    r=s.shapes.add_shape(MSO_SHAPE.RECTANGLE,0,0,prs.slide_width,prs.slide_height)
    r.fill.solid(); r.fill.fore_color.rgb=BG; r.line.fill.background()
    r.shadow.inherit=False
    return s

def tb(s,l,t,w,h,anchor=MSO_ANCHOR.TOP):
    b=s.shapes.add_textbox(Inches(l),Inches(t),Inches(w),Inches(h)); tf=b.text_frame
    tf.word_wrap=True; tf.vertical_anchor=anchor; return tf

def setpara(p,text,size,color,bold=False,font=BODY,align=PP_ALIGN.LEFT,spacing=1.0,after=0):
    p.text=text; p.alignment=align; p.line_spacing=spacing; p.space_after=Pt(after)
    for r in p.runs:
        r.font.size=Pt(size); r.font.bold=bold; r.font.name=font; r.font.color.rgb=color
    return p

def addpara(tf,text,size,color,bold=False,font=BODY,align=PP_ALIGN.LEFT,spacing=1.0,after=0,bullet=False):
    p=tf.add_paragraph(); return setpara(p,text,size,color,bold,font,align,spacing,after)

def first(tf,text,size,color,bold=False,font=BODY,align=PP_ALIGN.LEFT,spacing=1.0,after=0):
    return setpara(tf.paragraphs[0],text,size,color,bold,font,align,spacing,after)

def rrect(s,l,t,w,h,fill=BG2,line=LINE,lw=1.0,shape=MSO_SHAPE.ROUNDED_RECTANGLE):
    sh=s.shapes.add_shape(shape,Inches(l),Inches(t),Inches(w),Inches(h))
    sh.shadow.inherit=False
    if fill is None: sh.fill.background()
    else: sh.fill.solid(); sh.fill.fore_color.rgb=fill
    if line is None: sh.line.fill.background()
    else: sh.line.color.rgb=line; sh.line.width=Pt(lw)
    try: sh.adjustments[0]=0.06
    except Exception: pass
    return sh

def eyebrow(s,text,y=0.5):
    first(tb(s,0.7,y,11.9,0.4),text.upper(),13,PETROL,bold=True,font=MONO)
def title(s,text,y=0.92,size=34,w=11.9):
    first(tb(s,0.7,y,w,1.5),text,size,INK,bold=True,font=HEAD,spacing=1.02)
def pic(s,path,l,t,w):
    im=Image.open(path); ar=im.height/im.width; ph=w*ar
    # white card behind
    rrect(s,l-0.12,t-0.12,w+0.24,ph+0.24,fill=WHITE,line=LINE,lw=1.0)
    s.shapes.add_picture(path,Inches(l),Inches(t),Inches(w))
    return ph

def card(s,l,t,w,h,kicker,kcolor,bodyfn):
    rrect(s,l,t,w,h,fill=BG2,line=LINE,lw=1.0)
    tf=tb(s,l+0.28,t+0.24,w-0.56,h-0.48)
    first(tf,kicker.upper(),11,kcolor,bold=True,font=MONO,after=6)
    bodyfn(tf)

# ---------------- 1 TITLE ----------------
s=slide()
eyebrow(s,"Development study · self-hosted coding agent",0.9)
first(tb(s,0.7,1.35,10.5,3.2),"Turning the prompt tax into GPU capacity",46,INK,bold=True,font=HEAD,spacing=1.02)
first(tb(s,0.7,4.7,9.6,1.2),"Compressing a coding agent’s fixed preamble into a handful of learned “gist” tokens: what it buys, what it costs, and what to fund next.",18,INK2,spacing=1.2)
tf=tb(s,0.7,6.1,11,0.9)
first(tf,"Arun Menon · arumenon@paypal.com",13,INK2,font=MONO)
addpara(tf,"Claude Code → proxy → vLLM → Qwen3.8-27B (hybrid attention) · one GPU",12,PETROL,font=MONO,after=0)

# ---------------- 2 BLUF ----------------
s=slide(); eyebrow(s,"Bottom line up front"); title(s,"The answer in four lines")
cw,gap=2.85,0.2; x0=0.7; y=2.1; ch=3.9
cards=[("The tax",COPPER,"At every step, the coding agent (Claude Code) re-sends the same fixed preamble to the model: ~17.5–21k tokens, over 90% tool schemas, about 0.72 of a short session."),
       ("The lever",PLUM,"Replace it with a few thousand learned tokens. Base model frozen; deployed in a proxy, no client or engine change."),
       ("The measurement",PETROL,"H100 finite-window replay: 2x the target rate passing the latency criterion and +44% observed peak throughput. Mechanism and deployment savings remain unestablished."),
       ("The caveat",WARN,"A development study: the lever is real; the dollar-per-session number is not proven yet.")]
for i,(k,c,body) in enumerate(cards):
    card(s,x0+i*(cw+gap),y,cw,ch,k,c,lambda tf,b=body:first(tf,b,15,INK,spacing=1.15))
first(tb(s,0.7,6.25,11.9,0.6),"You can stop here. The rest is the evidence, the catch, and what it would take to bank the saving.",12.5,INK2)

# ---------------- 3 WHY TCO ----------------
s=slide(); eyebrow(s,"The cost lens"); title(s,"Why this is a total-cost question")
first(tb(s,0.7,2.0,11.6,1.0),"For a self-hosted agent, serving cost is driven by how many tokens the model reads per turn, which caps how many sessions a GPU can carry. Three cost drivers; gisting acts on the first.",17,INK2,spacing=1.2)
cw=3.75; y=3.4; ch=2.9
c3=[("GPU capacity  ← gisting acts here",PETROL,"Shorter prompts change the work the server performs. Mechanism and deployment value remain open. Replay: 2x the target rate passed the chosen criterion.",PETROL2),
    ("Engineering",INK2,"One-time: build the proxy, the template, and the training loop. The loop is reusable across models.",LINE),
    ("Risk",INK2,"Compressed rules are harder to audit; the benefit is model-dependent. Managed, not eliminated.",LINE)]
for i,(k,c,body,ln) in enumerate(c3):
    sh=rrect(s,0.7+i*(cw+0.2),y,cw,ch,fill=BG2,line=ln,lw=1.25 if ln==PETROL2 else 1.0)
    tf=tb(s,0.7+i*(cw+0.2)+0.28,y+0.24,cw-0.56,ch-0.48)
    first(tf,k.upper(),11,c,bold=True,font=MONO,after=8); addpara(tf,body,15,INK,spacing=1.15)

# ---------------- 4 THE TAX ----------------
s=slide(); eyebrow(s,"The tax, measured"); title(s,"Most of every turn is machine-readable boilerplate")
by,bh,total=2.5,1.15,11.9; cx=0.7
for name,sub,frac,col in [("Tool schemas","~16,000 tokens  ·  >90% of the block",0.78,PETROL2),("Rules","~1.3k",0.09,COPPER),("Per-session","kept raw",0.13,RGBColor(0x2b,0x3a,0x41))]:
    w=total*frac; rrect(s,cx,by,w-0.03,bh,fill=col,line=None,shape=MSO_SHAPE.RECTANGLE)
    tf=tb(s,cx+0.18,by,w-0.36,bh,anchor=MSO_ANCHOR.MIDDLE)
    first(tf,name,14 if frac>0.2 else 11,WHITE,bold=True,after=2)
    addpara(tf,sub,10 if frac>0.2 else 8.5,WHITE)
    cx+=w
ny=4.25
for i,(n,c,u) in enumerate([("17.5–21k",COPPER,"fixed tokens per turn"),(">90%",COPPER,"is tool schemas, not rules"),("0.72",PETROL,"of a short session’s input")]):
    first(tb(s,0.7+i*4.0,ny,3.8,0.7),n,30,c,bold=True,font=MONO)
    first(tb(s,0.7+i*4.0,ny+0.62,3.8,0.5),u,12,INK2,font=MONO)
first(tb(s,0.7,5.7,11.9,0.6),"The coding-agent harness prepends the same block, byte-for-byte, on every model call. Per-session values (paths, git status, date) are split out and kept raw.",13,INK2)

# ---------------- 5 THE IDEA ----------------
s=slide(); eyebrow(s,"The lever"); title(s,"Teach the model a shorthand for the boilerplate")
steps=[("01","Grow the vocabulary","Add a few thousand new “gist” tokens, seeded from the block they replace."),
       ("02","Self-distil","The model matches its own behaviour (short gist vs. full block). All base weights frozen; only the new rows train."),
       ("03","Serve via a proxy","The proxy swaps the span for gist tokens. No change to the client or the engine.")]
sw,gap,y,h=3.7,0.35,2.7,3.2
for i,(n,t,b) in enumerate(steps):
    l=0.7+i*(sw+gap); rrect(s,l,y,sw,h,fill=BG2,line=LINE)
    tf=tb(s,l+0.32,y+0.32,sw-0.64,h-0.64)
    first(tf,n,12,PETROL,bold=True,font=MONO,after=6)
    addpara(tf,t,20,WHITE,bold=True,font=HEAD,after=10)
    addpara(tf,b,14,INK2,spacing=1.2)
    if i<2: first(tb(s,l+sw-0.02,y+h/2-0.35,gap+0.1,0.7,anchor=MSO_ANCHOR.MIDDLE),"→",26,PETROL,bold=True,align=PP_ALIGN.CENTER)
first(tb(s,0.7,6.15,11.9,0.6),"The only trained object is a small embedding tensor: cheap to produce, cheap to serve.",13,INK2)

# ---------------- 6 PARITY ----------------
s=slide(); eyebrow(s,"Proof · parity"); title(s,"The short prompt matched the full prompt")
chips=[("2:1","12 / 12"),("4:1","12 / 12"),("8:1","12 / 12"),("16:1","12 / 12")]
for i,(r,sc) in enumerate(chips):
    rrect(s,0.7+i*2.2,2.2,1.9,1.3,fill=BG2,line=PETROL2,lw=1.25)
    tf=tb(s,0.7+i*2.2,2.35,1.9,1.1,anchor=MSO_ANCHOR.MIDDLE)
    first(tf,r,22,PETROL,bold=True,font=MONO,align=PP_ALIGN.CENTER,after=2)
    addpara(tf,sc,13,GOOD,font=MONO,align=PP_ALIGN.CENTER)
first(tb(s,0.7,4.1,11.4,1.3),"Every compression ratio and the full prompt scored a perfect 12 / 12 on the task suite, while input dropped from ~24k to ~9–11k tokens per turn.",18,INK2,spacing=1.25)
rrect(s,0.7,5.7,4.6,0.55,fill=None,line=RGBColor(0x5a,0x4a,0x24),lw=1.0)
first(tb(s,0.85,5.78,4.4,0.4),"single run · small, partly-reused suite",12,WARN,font=MONO)

# ---------------- 8 PAYOFF (native line chart, measured) ----------------
s=slide(); eyebrow(s,"The payoff (measured)"); title(s,"Finite-window serving measurements")
cd=CategoryChartData(); cd.categories=["1","2","4","8","16","32","48","64"]
cd.add_series("full prompt",(13.1,22.7,36.9,34.7,42.7,42.7,32.0,29.3)); cd.add_series("gist 8:1",(14.7,25.3,42.7,48.0,59.3,61.3,52.7,41.3))
gf=s.shapes.add_chart(XL_CHART_TYPE.LINE_MARKERS,Inches(0.7),Inches(2.1),Inches(7.4),Inches(4.6),cd)
ch=gf.chart; ch.has_title=True; ch.chart_title.text_frame.text="requests / minute vs concurrent sessions  (H100 NVL, tuned server, 3 repeats)"
for r in ch.chart_title.text_frame.paragraphs[0].runs: r.font.size=Pt(12); r.font.color.rgb=INK2; r.font.name=MONO; r.font.bold=False
ch.has_legend=True; ch.legend.position=XL_LEGEND_POSITION.TOP; ch.legend.include_in_layout=False; ch.legend.font.color.rgb=INK2; ch.legend.font.size=Pt(12)
ser=ch.plots[0].series
ser[0].format.line.color.rgb=SLATE; ser[0].format.line.width=Pt(3); ser[1].format.line.color.rgb=PLUM; ser[1].format.line.width=Pt(3)
for ax in (ch.category_axis,ch.value_axis):
    ax.tick_labels.font.color.rgb=INK2; ax.tick_labels.font.size=Pt(12); ax.format.line.color.rgb=LINE
ch.value_axis.has_major_gridlines=True; ch.value_axis.major_gridlines.format.line.color.rgb=RGBColor(0x1b,0x26,0x2b)
tf=tb(s,8.4,2.2,4.3,4.4)
first(tf,"2x",30,PLUM,bold=True,font=MONO,after=2); addpara(tf,"target rate passing the latency criterion (18 → 36 req/min)",12,INK2,font=MONO,after=12)
addpara(tf,"+44%",30,PETROL,bold=True,font=MONO,after=2); addpara(tf,"peak throughput, same GPU (42.7 → 61.3 req/min)",12,INK2,font=MONO,after=14)
addpara(tf,"The advantage grows with load (1.12x at 1 session → 1.65x at 48) and is incremental over prefix caching: 2–4x larger when caching can't help. J10: 202 runs across both GPUs, 0 request errors.",14,INK,spacing=1.2)

# ---------------- 9 WHY CAPACITY ----------------
s=slide(); eyebrow(s,"Correction · J11"); title(s,"The residency explanation was wrong")
first(tb(s,0.7,2.0,11.6,1.1),'External review found a 100-connection limit in our load generator. J11 removed it and measured 123 to 137 simultaneous requests on the H200. We withdrew the hardware-ceiling explanation. The cause of the throughput difference remains under investigation.',17,INK2,spacing=1.2)
gx,gy,cell,gp=0.7,3.5,0.42,0.1
for k in range(64):
    col=k%16; row=k//16
    c=PETROL if k<16 else RGBColor(0x24,0x30,0x36)
    rrect(s,gx+col*(cell+gp),gy+row*(cell+gp),cell,cell,fill=c,line=None,shape=MSO_SHAPE.ROUNDED_RECTANGLE)
first(tb(s,0.7,5.8,11.6,1.15),'Architecture: 16 full-attention layers and 48 linear-attention layers. This diagram does not establish a residency mechanism. J11 measured 137 gist versus 126 full at 256 offered requests, with nearly full cache. Lifting the cap reduced throughput in three of four comparisons. One run per condition; no quality test.',12.5,INK2,spacing=1.15)

# ---------------- 9b THE COST LEVER ----------------
s=slide(); eyebrow(s,"Corrected cost comparison"); title(s,"Similar replay output per rental dollar")
for i,(n,c,u) in enumerate([("16.16",SLATE,"H100 · full prompt"),("23.23",PLUM,"H100 · gist 8:1"),("23.38",PETROL,"H200 · full prompt"),("22.83",SLATE,"H200 · gist 8:1")]):
    first(tb(s,0.7+i*3.0,2.2,2.8,0.8),n,34,c,bold=True,font=MONO); first(tb(s,0.7+i*3.0,2.95,2.8,0.5),u,12,INK2,font=MONO)
first(tb(s,0.7,3.55,11.9,0.5),"peak replay req/min per ($/h), quoted prices: H100 $2.64/h; H200 $3.65/h",12,INK2,font=MONO)
first(tb(s,0.7,4.2,11.9,1.25),"H200 with the full prompt gives 23.38, slightly above H100 with gist at 23.23. Earlier figures mixed quoted and effective prices. Cheaper-card substitution is not established.",17,INK,spacing=1.25)
first(tb(s,0.7,5.65,11.9,1.2),"These peaks are finite-window replay measurements, with unequal hardware tuning and no quality test at load. Prefix-cache hit rates also differ: full 0.791 to 0.840, gist 0.580 to 0.626 in J11. The higher cached fraction favours full on that metric; its effect on the comparison was not controlled.",13,INK2,spacing=1.15)

# ---------------- 10 THE LAB ----------------
s=slide(); eyebrow(s,"The capability"); title(s,"We built the lab, not just the result")
y,h=2.8,1.05; cx=0.7
nodes=[("Provision GPU",2.0),("Train",1.35),("Serve",1.35),("Evaluate",1.7),("Destroy",1.5)]
for i,(n,w) in enumerate(nodes):
    rrect(s,cx,y,w,h,fill=BG2,line=LINE); tf=tb(s,cx,y,w,h,anchor=MSO_ANCHOR.MIDDLE); first(tf,n,14,WHITE,bold=True,align=PP_ALIGN.CENTER)
    cx+=w
    ch,cc=("→",PETROL) if i<len(nodes)-1 else ("↺",COPPER)
    first(tb(s,cx,y,0.55,h,anchor=MSO_ANCHOR.MIDDLE),ch,20,cc,bold=True,align=PP_ALIGN.CENTER); cx+=0.55
rrect(s,cx,y,1.7,h,fill=None,line=RGBColor(0x3a,0x4a,0x51)); tf=tb(s,cx,y,1.7,h,anchor=MSO_ANCHOR.MIDDLE); first(tf,"next recipe",13,INK2,align=PP_ALIGN.CENTER)
rrect(s,0.7,4.35,11.9,0.95,fill=RGBColor(0x22,0x1a,0x11),line=RGBColor(0x5a,0x4a,0x2a))
first(tb(s,0.95,4.35,11.4,0.95,anchor=MSO_ANCHOR.MIDDLE),"SPEND-SAFETY · structural  ·  idle watchdog · ledger at creation · sync-before-destroy · global deadline",13,COPPER,font=MONO)
first(tb(s,0.7,5.6,11.9,0.8),"One detached controller drives every recipe end to end, unattended. Makes the next model cheap to try: the capability outlasts this study.",14,INK2,spacing=1.2)

# ---------------- 11 LEDGER ----------------
s=slide(); eyebrow(s,"Honest ledger"); title(s,"What’s proven, what isn’t")
proven=["Equal task scores on our suites, every ratio.","Half-to-two-thirds fewer tokens read per turn.","Finite-window H100 replay: 2x target rate, +44% observed peak.","Cache-off advantage observed on H100; mechanism unestablished.","Quoted-price comparison corrected; J11 withdraws the H200 ceiling explanation."]
notyet=["Generalisation, sustained capacity and savings on unseen work.","Per-hardware tuning (the H200 ran an H100-tuned config; one regression at 16 sessions).","Rare-tool reach (left unscored by harness faults).","Audit guarantees that compressed rules still bind."]
def col(l,kicker,kc,items,linec):
    rrect(s,l,2.15,5.75,4.35,fill=BG2,line=linec,lw=1.0)
    tf=tb(s,l+0.3,2.4,5.15,3.9); first(tf,kicker.upper(),12,kc,bold=True,font=MONO,after=10)
    for it in items: addpara(tf,"▪  "+it,14,INK,spacing=1.12,after=7)
col(0.7,"Established here",GOOD,proven,RGBColor(0x2c,0x50,0x40))
col(6.85,"Not yet",WARN,notyet,RGBColor(0x5a,0x4a,0x24))
first(tb(s,0.7,6.65,11.9,0.5),"An independent adversarial review of the whole program was run and folded into the writeup.",12,INK2)

# ---------------- 12 THE ASK ----------------
s=slide(); eyebrow(s,"The ask"); title(s,"From “real lever” to a number you can budget")
asks=[("1 · Validate","A held-out eval with paired, repeated runs. Is the parity real beyond our own tasks?"),
      ("2 · Tune per hardware","Tune both prompt versions on each GPU and re-measure with explicit admission limits. The current results are finite-window replay observations."),
      ("3 · Pilot","A guarded rollout with explicit rule-audit and write-target checks at the serving boundary.")]
cw=3.75
for i,(k,body) in enumerate(asks):
    card(s,0.7+i*(cw+0.2),2.2,cw,3.4,k,PETROL,lambda tf,b=body:first(tf,b,15,INK,spacing=1.2))
first(tb(s,0.7,6.0,11.9,0.7),"Validate quality and sustained performance before a pilot. J11 corrects one instrument defect; the other review findings remain open.",13,INK2)

# ---------------- 13 DECISION ----------------
s=slide(); eyebrow(s,"Decision"); title(s,"Validate the deployment case")
first(tb(s,0.7,2.3,10.5,1.6),"Fund validation of quality, sustained performance and cost before a guarded pilot.",30,WHITE,bold=True,font=HEAD,spacing=1.1)
first(tb(s,0.7,4.2,11.2,1.4),"H100 replay recorded 2x the target rate passing the latency criterion and +44% observed peak throughput. J11 withdrew the residency explanation. The corrected cost comparison does not establish cheaper-card substitution. Those open questions determine the next experiment.",17,INK2,spacing=1.25)
first(tb(s,0.7,6.2,11.9,0.5),"GitHub: arunmenon/gisting-coding-agent  ·  weights & data on Hugging Face (private)",12,PETROL,font=MONO)

# ---------------- APPENDIX: THE FAILURE ----------------
s=slide(); eyebrow(s,"Appendix · the failure we caught"); title(s,"The failure that mattered, and the fix")
def pill(l,t,w,txt,tc,lc,h=0.82):
    rrect(s,l,t,w,h,fill=BG2,line=lc); tf=tb(s,l+0.2,t,w-0.4,h,anchor=MSO_ANCHOR.MIDDLE)
    first(tf,txt,13,tc,font=MONO,spacing=1.05)
def arrow(l,t,ch="→",c=PETROL,w=0.5,h=0.82):
    first(tb(s,l,t,w,h,anchor=MSO_ANCHOR.MIDDLE),ch,20,c,bold=True,align=PP_ALIGN.CENTER)
PLUMLN=RGBColor(0x5a,0x3f,0x6e); BADLN=RGBColor(0x6e,0x3a,0x3a); OKLN=RGBColor(0x2c,0x50,0x40)
first(tb(s,0.7,2.55,1.4,0.5),"BEFORE",13,WARN,bold=True,font=MONO)
pill(2.2,2.4,4.3,"gist: rules + …/<session-id>/",PLUM,PLUMLN)
arrow(6.6,2.4)
pill(7.2,2.4,5.1,"writes to an invented directory   ×",RGBColor(0xe7,0x91,0x91),BADLN)
first(tb(s,0.7,3.75,1.4,0.5),"AFTER",13,GOOD,bold=True,font=MONO)
pill(2.2,3.6,2.3,"gist: rules",PLUM,PLUMLN)
arrow(4.55,3.6,"+",INK2,0.4)
pill(5.0,3.6,3.4,"raw: session path, date, model",INK,LINE)
arrow(8.5,3.6)
pill(9.1,3.6,3.2,"writes correctly   ✓",GOOD,OKLN)
first(tb(s,0.7,4.95,11.9,0.8),"Keeping session-specific values raw restored the score 11/16 → 16/16 at 8:1.",18,INK,spacing=1.2)
first(tb(s,0.7,5.95,11.9,0.6),"The productionization gotcha every deployment will hit, and evidence we were looking hard, not cherry-picking.",13,INK2)


prs.save(OUT)
print("saved",OUT,"slides",len(prs.slides._sldIdLst))
