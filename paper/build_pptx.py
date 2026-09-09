from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE
from pptx.chart.data import CategoryChartData
from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION
from PIL import Image
import os

FIG="/private/tmp/claude-501/-Users-arunmenon-projects-gisting/82deba89-c9a1-41e0-9e61-ec090b34e902/scratchpad/paper_figs"
OUT="/Users/arunmenon/projects/gisting/Gisting-CTO-deck.pptx"

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
first(tb(s,0.7,4.7,9.6,1.2),"Compressing a coding agent’s fixed preamble into a handful of learned “gist” tokens — what it buys, what it costs, and what to fund next.",18,INK2,spacing=1.2)
tf=tb(s,0.7,6.1,11,0.9)
first(tf,"Arun Menon · arumenon@paypal.com",13,INK2,font=MONO)
addpara(tf,"Claude Code → proxy → vLLM → Qwen3.8-27B (hybrid attention) · one GPU",12,PETROL,font=MONO,after=0)

# ---------------- 2 BLUF ----------------
s=slide(); eyebrow(s,"Bottom line up front"); title(s,"The answer in four lines")
cw,gap=2.85,0.2; x0=0.7; y=2.1; ch=3.9
cards=[("The tax",COPPER,"At every step, the coding agent (Claude Code) re-sends the same fixed preamble to the model — ~17.5–21k tokens, over 90% tool schemas, about 0.72 of a short session."),
       ("The lever",PLUM,"Replace it with a few thousand learned tokens. Base model frozen; deployed in a proxy, no client or engine change."),
       ("The payoff",PETROL,"~16% more throughput at eight concurrent sessions — capacity per GPU, not faster single replies."),
       ("The caveat",WARN,"A development study: the lever is real; the dollar-per-session number is not proven yet.")]
for i,(k,c,body) in enumerate(cards):
    card(s,x0+i*(cw+gap),y,cw,ch,k,c,lambda tf,b=body:first(tf,b,15,INK,spacing=1.15))
first(tb(s,0.7,6.25,11.9,0.6),"You can stop here. The rest is the evidence, the catch, and what it would take to bank the saving.",12.5,INK2)

# ---------------- 3 WHY TCO ----------------
s=slide(); eyebrow(s,"The cost lens"); title(s,"Why this is a total-cost question")
first(tb(s,0.7,2.0,11.6,1.0),"For a self-hosted agent, serving cost is driven by how many tokens the model reads per turn, which caps how many sessions a GPU can carry. Three cost drivers — gisting acts on the first.",17,INK2,spacing=1.2)
cw=3.75; y=3.4; ch=2.9
c3=[("GPU capacity  ← gisting acts here",PETROL,"Token-bound. Fewer input tokens per turn → more concurrent sessions per GPU before latency degrades.",PETROL2),
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
       ("02","Self-distil","The model matches its own behaviour — short gist vs. full block. All base weights frozen; only the new rows train."),
       ("03","Serve via a proxy","The proxy swaps the span for gist tokens. No change to the client or the engine.")]
sw,gap,y,h=3.7,0.35,2.7,3.2
for i,(n,t,b) in enumerate(steps):
    l=0.7+i*(sw+gap); rrect(s,l,y,sw,h,fill=BG2,line=LINE)
    tf=tb(s,l+0.32,y+0.32,sw-0.64,h-0.64)
    first(tf,n,12,PETROL,bold=True,font=MONO,after=6)
    addpara(tf,t,20,WHITE,bold=True,font=HEAD,after=10)
    addpara(tf,b,14,INK2,spacing=1.2)
    if i<2: first(tb(s,l+sw-0.02,y+h/2-0.35,gap+0.1,0.7,anchor=MSO_ANCHOR.MIDDLE),"→",26,PETROL,bold=True,align=PP_ALIGN.CENTER)
first(tb(s,0.7,6.15,11.9,0.6),"The only trained object is a small embedding tensor — cheap to produce, cheap to serve.",13,INK2)

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

# ---------------- 8 PAYOFF (native chart) ----------------
s=slide(); eyebrow(s,"The payoff"); title(s,"The saving shows up as capacity under load")
cd=CategoryChartData(); cd.categories=["c=1","c=4","c=8"]
cd.add_series("full prompt",(6.9,16.4,20.0)); cd.add_series("gist",(7.2,18.9,23.2))
gf=s.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED,Inches(0.7),Inches(2.1),Inches(7.4),Inches(4.6),cd)
ch=gf.chart; ch.has_title=True; ch.chart_title.text_frame.text="requests / minute  (higher is better)"
for r in ch.chart_title.text_frame.paragraphs[0].runs: r.font.size=Pt(12); r.font.color.rgb=INK2; r.font.name=MONO; r.font.bold=False
ch.has_legend=True; ch.legend.position=XL_LEGEND_POSITION.TOP; ch.legend.include_in_layout=False
ch.legend.font.color.rgb=INK2; ch.legend.font.size=Pt(12)
ser=ch.plots[0].series
ser[0].format.fill.solid(); ser[0].format.fill.fore_color.rgb=SLATE
ser[1].format.fill.solid(); ser[1].format.fill.fore_color.rgb=PETROL
ch.plots[0].has_data_labels=True; ch.plots[0].data_labels.font.size=Pt(11); ch.plots[0].data_labels.font.color.rgb=INK
for ax in (ch.category_axis,ch.value_axis):
    ax.tick_labels.font.color.rgb=INK2; ax.tick_labels.font.size=Pt(12); ax.format.line.color.rgb=LINE
ch.value_axis.has_major_gridlines=True; ch.value_axis.major_gridlines.format.line.color.rgb=RGBColor(0x1b,0x26,0x2b)
tf=tb(s,8.4,2.4,4.2,4.0)
first(tf,"Throughput rises with concurrency — and the gain grows as the service gets busier. A single reply is barely faster.",16,INK,spacing=1.2,after=14)
addpara(tf,"For a shared internal agent service, this is sessions per GPU — the number that sets cost.",14,INK2,spacing=1.2,after=10)
addpara(tf,"One replay; direction, not precision.",12,INK2,font=MONO)

# ---------------- 9 WHY CAPACITY ----------------
s=slide(); eyebrow(s,"The catch · architecture"); title(s,"Why it’s capacity, not speed")
first(tb(s,0.7,2.0,11.6,1.1),"This model uses full attention in only 16 of its 64 layers. A shorter prompt saves decode work only there — so the win is more sessions in parallel, not a faster individual answer.",17,INK2,spacing=1.2)
gx,gy,cell,gp=0.7,3.5,0.42,0.1
for k in range(64):
    col=k%16; row=k//16
    c=PETROL if k<16 else RGBColor(0x24,0x30,0x36)
    rrect(s,gx+col*(cell+gp),gy+row*(cell+gp),cell,cell,fill=c,line=None,shape=MSO_SHAPE.ROUNDED_RECTANGLE)
first(tb(s,0.7,5.9,11.6,0.9),"■ full-attention layers (where a shorter prompt helps)      ■ linear-attention layers (fixed-size state).  The benefit is architecture-dependent: a different model shifts it.",12.5,INK2,spacing=1.2)

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
first(tb(s,0.95,4.35,11.4,0.95,anchor=MSO_ANCHOR.MIDDLE),"SPEND-SAFETY · structural  —  idle watchdog · ledger at creation · sync-before-destroy · global deadline",13,COPPER,font=MONO)
first(tb(s,0.7,5.6,11.9,0.8),"One detached controller drives every recipe end to end, unattended. Makes the next model cheap to try — the capability outlasts this study.",14,INK2,spacing=1.2)

# ---------------- 11 LEDGER ----------------
s=slide(); eyebrow(s,"Honest ledger"); title(s,"What’s proven, what isn’t")
proven=["Equal task scores on our suites, every ratio.","Half-to-two-thirds fewer tokens read per turn.","Throughput rises under load; the fix removes the path failure.","The tooling works end to end."]
notyet=["Generalisation on unseen, held-out work.","A saturation test → a real sessions-per-GPU / $ number.","The cause of the serving gain (a hypothesis).","Rare-tool reach (left unscored by harness faults).","Audit guarantees that compressed rules still bind."]
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
      ("2 · Quantify","A saturation test under sustained load. Converts “throughput direction” into sessions per GPU and a cost per session."),
      ("3 · Pilot","A guarded rollout with explicit rule-audit and write-target checks at the serving boundary.")]
cw=3.75
for i,(k,body) in enumerate(asks):
    card(s,0.7+i*(cw+0.2),2.2,cw,3.4,k,PETROL,lambda tf,b=body:first(tf,b,15,INK,spacing=1.2))
first(tb(s,0.7,6.0,11.9,0.7),"Bounded effort: a single GPU over days, not a new research program — the loop and serving path already exist.",13,INK2)

# ---------------- 13 DECISION ----------------
s=slide(); eyebrow(s,"Decision"); title(s,"The lever is real and cheap to prototype")
first(tb(s,0.7,2.3,10.5,1.6),"Fund a short validation — eval + saturation — before any production commitment.",30,WHITE,bold=True,font=HEAD,spacing=1.1)
first(tb(s,0.7,4.2,11.2,1.4),"The tooling exists, the risk is contained, and the upside is GPU capacity that compounds under load. What’s missing is a validated number, and that is days of work away, not months.",17,INK2,spacing=1.25)
first(tb(s,0.7,6.2,11.9,0.5),"GitHub: arunmenon/gisting-coding-agent  ·  weights & data on Hugging Face (private)",12,PETROL,font=MONO)

# ---------------- APPENDIX: THE FAILURE ----------------
s=slide(); eyebrow(s,"Appendix · the failure we caught"); title(s,"The failure that mattered — and the fix")
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
first(tb(s,0.7,5.95,11.9,0.6),"The productionization gotcha every deployment will hit — and evidence we were looking hard, not cherry-picking.",13,INK2)


prs.save(OUT)
print("saved",OUT,"slides",len(prs.slides._sldIdLst))
