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

PLUMLN=RGBColor(0x5a,0x3f,0x6e); BADLN=RGBColor(0x6e,0x3a,0x3a); OKLN=RGBColor(0x2c,0x50,0x40); WARNLN=RGBColor(0x5a,0x4a,0x24)
def cards(s,items,y,h,n,size=15,cw=None,gap=0.2):
    cw=cw or (11.9-gap*(n-1))/n
    for i,it in enumerate(items):
        k,c,body=it[:3]; ln=it[3] if len(it)>3 else LINE
        l=0.7+i*(cw+gap); rrect(s,l,y,cw,h,fill=BG2,line=ln,lw=1.25 if ln!=LINE else 1.0)
        tf=tb(s,l+0.28,y+0.24,cw-0.56,h-0.48)
        first(tf,k.upper(),11,c,bold=True,font=MONO,after=6)
        if len(it)>4: addpara(tf,it[4],11,INK2,font=MONO,after=6)
        addpara(tf,body,size,INK,spacing=1.15)
def caption(s,text,y=6.3,size=13):
    first(tb(s,0.7,y,11.9,0.8),text,size,INK2,spacing=1.15)
def tag(s,text,y,w=4.6,col=WARN,ln=WARNLN):
    rrect(s,0.7,y,w,0.5,fill=None,line=ln,lw=1.0); first(tb(s,0.85,y+0.06,w-0.2,0.4),text,12,col,font=MONO)

# 1 TITLE
s=slide()
eyebrow(s,"Lattice · cost optimization · new pillar",0.9)
first(tb(s,0.7,1.35,11.5,2.6),"Gisting: cutting the prompt tax every agent call pays",44,INK,bold=True,font=HEAD,spacing=1.02)
first(tb(s,0.7,4.2,10.5,1.3),"A learned shorthand for the fixed preamble a coding-agent harness re-sends on every model call. Proven on one harness and model pairing, and built to carry to the others.",18,INK2,spacing=1.2)
tf=tb(s,0.7,6.0,11.5,0.9)
first(tf,"Arun Menon · arumenon@paypal.com",13,INK2,font=MONO)
addpara(tf,"First pairing: Claude Code → proxy → vLLM → Qwen3.8-27B (open weights, self-hosted)",12,PETROL,font=MONO)

# 2 BLUF
s=slide(); eyebrow(s,"Bottom line up front"); title(s,"The answer in four lines")
cards(s,[("Where it fits",PETROL,"A fourth Lattice lever. Routing and distillation cut cost per token; the meta-harness shapes calls. Gisting cuts the fixed tokens every call carries."),
         ("What we showed",PLUM,"On Claude Code with Qwen: task scores held at every compression ratio, input per turn more than halved, and on an H100 2x the request rate within the latency target, +44% peak throughput."),
         ("What it isn’t yet",WARN,"One pairing, our own task suite, short replay windows. Savings per task are not proven, and the mechanism is still open."),
         ("The ask",GOOD,"Take the recipe to a second harness and model pairing through the meta-harness, validate on held-out work, then a guarded pilot.")],2.1,4.2,4,size=14.5)

# 3 LATTICE MAP
s=slide(); eyebrow(s,"Where gisting sits in Lattice"); title(s,"Four levers on one cost equation")
cx=0.7
for txt,hot in [("cost per task",0),("=",-1),("calls",0),("×",-1),("tokens per call",1),("×",-1),("cost per token",0)]:
    if hot<0: first(tb(s,cx,2.05,0.45,0.6,anchor=MSO_ANCHOR.MIDDLE),txt,20,PETROL,bold=True,font=MONO,align=PP_ALIGN.CENTER); cx+=0.45; continue
    w=0.3+0.155*len(txt); rrect(s,cx,2.05,w,0.6,fill=BG2,line=PLUMLN if hot else LINE)
    first(tb(s,cx,2.05,w,0.6,anchor=MSO_ANCHOR.MIDDLE),txt,16,PLUM if hot else INK,font=MONO,align=PP_ALIGN.CENTER); cx+=w+0.1
cards(s,[("Lattice meta-harness",PETROL,"One adapter from any harness to any model. The control point for how calls are made and which model serves them.",LINE,"calls · where they land"),
         ("Gisting · this pillar",PLUM,"Learned shorthand for the preamble every call repeats: tool schemas and rules.",PLUMLN,"fixed tokens per call"),
         ("Adaptive routing",PETROL,"Sends each request to the cheapest model that can handle it.",LINE,"cost per token"),
         ("Model distillation",PETROL,"Smaller student models for the work that allows it.",LINE,"cost per token")],3.0,2.9,4,size=14)
caption(s,"The levers multiply rather than compete. A distilled model reached through the router still reads the full preamble on every call, unless it is gisted.",6.2)

# 4 THE TAX
s=slide(); eyebrow(s,"The tax"); title(s,"Most of every call is the same boilerplate")
by,bh,total=2.5,1.15,11.9; cx=0.7
for name,sub,frac,col in [("Tool schemas","~16,000 tokens  ·  >90% of the block",0.78,PETROL2),("Rules","~1.3k",0.09,COPPER),("Per-session","kept raw",0.13,RGBColor(0x2b,0x3a,0x41))]:
    w=total*frac; rrect(s,cx,by,w-0.03,bh,fill=col,line=None,shape=MSO_SHAPE.RECTANGLE)
    tf=tb(s,cx+0.18,by,w-0.36,bh,anchor=MSO_ANCHOR.MIDDLE)
    first(tf,name,14 if frac>0.2 else 11,WHITE,bold=True,after=2); addpara(tf,sub,10 if frac>0.2 else 8.5,WHITE)
    cx+=w
for i,(n,c,u) in enumerate([("17.5–21k",COPPER,"fixed tokens on every call"),(">90%",COPPER,"is tool schemas, not rules"),("0.72",PETROL,"of a short session’s input")]):
    first(tb(s,0.7+i*4.0,4.25,3.8,0.7),n,30,c,bold=True,font=MONO); first(tb(s,0.7+i*4.0,4.87,3.8,0.5),u,12,INK2,font=MONO)
caption(s,"Measured on Claude Code with the Qwen tokenizer. Any harness that exposes tools pays a version of this, but its size and makeup differ, so every new pairing starts with the same span study.",5.8)

# 5 THE RECIPE
s=slide(); eyebrow(s,"The recipe"); title(s,"Four steps, most of them reusable")
steps=[("00 · PER PAIRING","Study the span","Measure what that harness re-sends, what is fixed and what is per-session, and its share of each call."),("01","Grow the vocabulary","Add a few thousand new “gist” tokens, seeded from the block they replace."),
       ("02","Self-distil","The model learns to behave the same on the short form. Base weights frozen; only the new rows train."),
       ("03","Swap in a proxy","The proxy replaces the preamble with gist tokens. No change to the harness or the engine.")]
sw,gap,y,h=2.7,0.35,2.05,2.45
for i,(n,t,b) in enumerate(steps):
    l=0.7+i*(sw+gap); rrect(s,l,y,sw,h,fill=BG2,line=LINE); tf=tb(s,l+0.3,y+0.25,sw-0.6,h-0.5)
    first(tf,n,12,COPPER if i==0 else PETROL,bold=True,font=MONO,after=4); addpara(tf,t,18,WHITE,bold=True,font=HEAD,after=6); addpara(tf,b,12.5,INK2,spacing=1.12)
    if i<3: first(tb(s,l+sw-0.02,y+h/2-0.35,gap+0.1,0.7,anchor=MSO_ANCHOR.MIDDLE),"→",26,PETROL,bold=True,align=PP_ALIGN.CENTER)
cards(s,[("Portable across pairings",GOOD,"Training loop, proxy, evaluation harness, and the automated GPU lab that runs them.",OKLN),
         ("Redone per pairing",COPPER,"The span study for that harness and its tokenizer, then new rows trained for that model. Needs open weights we host; closed models get provider prompt caching instead.",RGBColor(0x5a,0x40,0x2a))],4.75,1.85,2,size=14)

# 6 PROOF
s=slide(); eyebrow(s,"Proof on the first pairing · Claude Code × Qwen3.8"); title(s,"The short prompt did the same work")
for i,(r,sc) in enumerate([("2:1","12 / 12"),("4:1","12 / 12"),("8:1","12 / 12"),("16:1","12 / 12")]):
    rrect(s,0.7+i*2.2,2.1,1.9,1.2,fill=BG2,line=PETROL2,lw=1.25); tf=tb(s,0.7+i*2.2,2.2,1.9,1.0,anchor=MSO_ANCHOR.MIDDLE)
    first(tf,r,22,PETROL,bold=True,font=MONO,align=PP_ALIGN.CENTER,after=2); addpara(tf,sc,13,GOOD,font=MONO,align=PP_ALIGN.CENTER)
first(tb(s,0.7,3.6,11.6,1.2),"Every compression ratio matched the full prompt on the task suite, while input per turn fell from ~24k to ~9–11k tokens. We run at 8:1: 16:1 bought only about 60% of the serving gain for more risk.",17,INK2,spacing=1.2)
first(tb(s,0.7,4.85,11.6,0.9),"The one failure that mattered: session values such as the working path must stay raw. Fixing that took a harder suite from 11/16 to 16/16.",17,INK2,spacing=1.2)
tag(s,"single runs · small, partly reused suites",6.0,4.8)

# 7 PAYOFF
s=slide(); eyebrow(s,"The payoff"); title(s,"More work from the same GPU")
cd=CategoryChartData(); cd.categories=["1","2","4","8","16","32","48","64"]
cd.add_series("full prompt",(13.1,22.7,36.9,34.7,42.7,42.7,32.0,29.3)); cd.add_series("gist 8:1",(14.7,25.3,42.7,48.0,59.3,61.3,52.7,41.3))
gf=s.shapes.add_chart(XL_CHART_TYPE.LINE_MARKERS,Inches(0.7),Inches(2.1),Inches(7.4),Inches(4.6),cd)
ch=gf.chart; ch.has_title=True; ch.chart_title.text_frame.text="requests / minute vs concurrent sessions  (H100, mean of 3 repeats)"
for r in ch.chart_title.text_frame.paragraphs[0].runs: r.font.size=Pt(12); r.font.color.rgb=INK2; r.font.name=MONO; r.font.bold=False
ch.has_legend=True; ch.legend.position=XL_LEGEND_POSITION.TOP; ch.legend.include_in_layout=False; ch.legend.font.color.rgb=INK2; ch.legend.font.size=Pt(12)
ser=ch.plots[0].series
ser[0].format.line.color.rgb=SLATE; ser[0].format.line.width=Pt(3); ser[1].format.line.color.rgb=PLUM; ser[1].format.line.width=Pt(3)
for ax in (ch.category_axis,ch.value_axis):
    ax.tick_labels.font.color.rgb=INK2; ax.tick_labels.font.size=Pt(12); ax.format.line.color.rgb=LINE
ch.value_axis.has_major_gridlines=True; ch.value_axis.major_gridlines.format.line.color.rgb=RGBColor(0x1b,0x26,0x2b)
tf=tb(s,8.4,2.2,4.3,4.6)
first(tf,"2x",30,PLUM,bold=True,font=MONO,after=2); addpara(tf,"request rate within the latency target (18 → 36 req/min)",12,INK2,font=MONO,after=12)
addpara(tf,"+44%",30,PETROL,bold=True,font=MONO,after=2); addpara(tf,"peak throughput, same H100 (42.7 → 61.3 req/min)",12,INK2,font=MONO,after=14)
addpara(tf,"A capacity lever, not a speed lever: a single reply is barely faster. The gain comes on top of prefix caching.",14,INK,spacing=1.2,after=10)
addpara(tf,"Short replay windows on one GPU class. On a larger H200 the peak gain was near zero, and the per-dollar comparison came out roughly even (appendix).",11.5,INK2,spacing=1.15)

# 8 STACKING
s=slide(); eyebrow(s,"How it compounds with Lattice"); title(s,"Built to plug into the other pillars")
cards(s,[("Meta-harness",PETROL,"The adapter already sits between harness and model. The gist swap is a proxy step, so it can live there and serve every harness routed through it."),
         ("Distillation",PETROL,"A student model still reads the full preamble on every call. The same recipe trains rows for the student: smaller model, shorter prompt."),
         ("Adaptive routing",PETROL,"A gisted endpoint becomes a cheaper target for the router, with the full-prompt path kept as a fallback.")],2.2,3.1,3,size=15)
tag(s,"design fit · not yet measured",5.65,3.6)

# 9 JETSTREAM
s=slide(); eyebrow(s,"Where it lands · Jetstream PDLC"); title(s,"Coding agents on many harnesses, many models")
cards(s,[("Inner loop · ticket to PR",PLUM,"Best fit. Many short agent steps, each re-sending the same tool preamble. The closest match to what we tested.",PLUMLN),
         ("Outer loop · vision, PRD, HLD",PETROL,"Smaller fit. Fewer, document-heavy calls, where the fixed preamble is a smaller share of each call."),
         ("Memory",PETROL,"Complementary. Memory is session-specific, so it stays raw; gisting covers only what never changes. That boundary is the lesson from our one real failure.")],2.2,3.1,3,size=15)
caption(s,"Applies to Jetstream traffic that reaches an open-weights model we host through the meta-harness. Calls to closed models keep using provider prompt caching.",5.65)

# 10 LEDGER
s=slide(); eyebrow(s,"Honest ledger"); title(s,"What’s proven, what isn’t")
def col(l,kicker,kc,items,linec):
    rrect(s,l,2.15,5.75,4.35,fill=BG2,line=linec,lw=1.0)
    tf=tb(s,l+0.3,2.4,5.15,3.9); first(tf,kicker.upper(),12,kc,bold=True,font=MONO,after=10)
    for it in items: addpara(tf,"▪  "+it,14.5,INK,spacing=1.12,after=8)
col(0.7,"Established",GOOD,["Equal task scores at every ratio on our suites.","Half to two thirds fewer tokens read per turn.","H100 replay: 2x rate within the latency target, +44% peak.","A reusable, spend-safe lab that runs the recipe end to end."],OKLN)
col(6.85,"Not yet",WARN,["A second harness and model pairing, including its span study.","Quality on held-out work, and at production load.","Savings per task, and why the gain happens. An external review withdrew our first explanation.","Audit that compressed rules still bind."],WARNLN)

# 11 THE LAB
s=slide(); eyebrow(s,"The capability"); title(s,"The next pairing is cheap to try")
y,h=2.6,1.05; cx=0.7
nodes=[("Provision GPU",2.0),("Train",1.35),("Serve",1.35),("Evaluate",1.7),("Destroy",1.5)]
for i,(n,w) in enumerate(nodes):
    rrect(s,cx,y,w,h,fill=BG2,line=LINE); first(tb(s,cx,y,w,h,anchor=MSO_ANCHOR.MIDDLE),n,14,WHITE,bold=True,align=PP_ALIGN.CENTER); cx+=w
    a,cc=("→",PETROL) if i<len(nodes)-1 else ("↺",COPPER)
    first(tb(s,cx,y,0.55,h,anchor=MSO_ANCHOR.MIDDLE),a,20,cc,bold=True,align=PP_ALIGN.CENTER); cx+=0.55
rrect(s,cx,y,1.7,h,fill=None,line=RGBColor(0x3a,0x4a,0x51)); first(tb(s,cx,y,1.7,h,anchor=MSO_ANCHOR.MIDDLE),"next pairing",13,INK2,align=PP_ALIGN.CENTER)
rrect(s,0.7,4.1,11.9,0.95,fill=RGBColor(0x22,0x1a,0x11),line=RGBColor(0x5a,0x4a,0x2a))
first(tb(s,0.95,4.1,11.4,0.95,anchor=MSO_ANCHOR.MIDDLE),"SPEND-SAFETY · structural  ·  idle watchdog · ledger at creation · sync-before-destroy · global deadline",13,COPPER,font=MONO)
caption(s,"One controller drives a recipe end to end, unattended. Swapping in a new harness or model changes the inputs, not the machinery.",5.4,14)

# 12 ASK
s=slide(); eyebrow(s,"The ask"); title(s,"Make gisting a Lattice pillar")
cards(s,[("1 · Second pairing",PLUM,"A Jetstream inner-loop harness on an open-weights model, through the meta-harness, starting with its span study. Proves the recipe carries.",PLUMLN),
         ("2 · Validate",PETROL,"Held-out tasks, repeated runs, and quality checked at production load."),
         ("3 · Guarded pilot",PETROL,"Inner loop, behind the meta-harness, with an automatic fallback to the full prompt.")],2.1,2.5,3,size=15)
first(tb(s,0.7,4.9,11.0,1.1),"The lever is real on one pairing. The next step is showing it travels.",26,WHITE,bold=True,font=HEAD,spacing=1.1)
first(tb(s,0.7,6.35,11.9,0.5),"White paper, code and results: GitHub arunmenon/gisting-coding-agent  ·  weights and data on Hugging Face (private)",12,PETROL,font=MONO)

# APPENDIX A
s=slide(); eyebrow(s,"Appendix A · a correction we made"); title(s,"Our first explanation of the gain was wrong")
first(tb(s,0.7,2.0,11.6,1.3),"External review found a 100-connection limit in our own load generator, and that limit, not the GPU, produced the number our explanation rested on. A follow-up with the limit removed confirmed it. We withdrew the explanation; the throughput figures measured below that limit stand.",16,INK2,spacing=1.2)
gx,gy,cell,gp=0.7,3.65,0.42,0.1
for k in range(64):
    rrect(s,gx+(k%16)*(cell+gp),gy+(k//16)*(cell+gp),cell,cell,fill=PETROL if k<16 else RGBColor(0x24,0x30,0x36),line=None)
caption(s,"The model mixes 16 full-attention layers with 48 linear-attention layers, which is why its behaviour under load differs from a standard transformer. Why the gist helps on it is still open.",5.9)

# APPENDIX B
s=slide(); eyebrow(s,"Appendix B · cost per rental dollar"); title(s,"Roughly even across the two cards")
for i,(n,c,u) in enumerate([("16.16",SLATE,"H100 · full prompt"),("23.23",PLUM,"H100 · gist 8:1"),("23.38",PETROL,"H200 · full prompt"),("22.83",SLATE,"H200 · gist 8:1")]):
    first(tb(s,0.7+i*3.0,2.2,2.8,0.8),n,34,c,bold=True,font=MONO); first(tb(s,0.7+i*3.0,2.95,2.8,0.5),u,12,INK2,font=MONO)
first(tb(s,0.7,3.55,11.9,0.5),"peak replay requests per minute per dollar-hour, quoted prices: H100 $2.64/h, H200 $3.65/h",12,INK2,font=MONO)
first(tb(s,0.7,4.3,11.9,1.3),"On the H100 the gist lifts output per dollar by about 44%. The H100 with the gist lands level with the H200 without it, so this does not yet show a cheaper card can replace a pricier one.",17,INK,spacing=1.25)

# APPENDIX C
s=slide(); eyebrow(s,"Appendix C · the failure we caught"); title(s,"What to keep out of the gist")
def pill(l,t,w,txt,tc,lc,h=0.82):
    rrect(s,l,t,w,h,fill=BG2,line=lc); first(tb(s,l+0.2,t,w-0.4,h,anchor=MSO_ANCHOR.MIDDLE),txt,13,tc,font=MONO,spacing=1.05)
def arrow(l,t,a="→",c=PETROL,w=0.5,h=0.82):
    first(tb(s,l,t,w,h,anchor=MSO_ANCHOR.MIDDLE),a,20,c,bold=True,align=PP_ALIGN.CENTER)
first(tb(s,0.7,2.55,1.4,0.5),"BEFORE",13,WARN,bold=True,font=MONO)
pill(2.2,2.4,4.3,"gist: rules + …/<session-id>/",PLUM,PLUMLN); arrow(6.6,2.4)
pill(7.2,2.4,5.1,"writes to an invented directory   ×",RGBColor(0xe7,0x91,0x91),BADLN)
first(tb(s,0.7,3.75,1.4,0.5),"AFTER",13,GOOD,bold=True,font=MONO)
pill(2.2,3.6,2.3,"gist: rules",PLUM,PLUMLN); arrow(4.55,3.6,"+",INK2,0.4)
pill(5.0,3.6,3.4,"raw: session path, date, model",INK,LINE); arrow(8.5,3.6)
pill(9.1,3.6,3.2,"writes correctly   ✓",GOOD,OKLN)
first(tb(s,0.7,4.95,11.9,0.8),"Keeping session-specific values raw restored the score 11/16 → 16/16 at 8:1.",18,INK,spacing=1.2)
caption(s,"Every new pairing will hit this boundary. It is also why memory and gisting are complementary rather than overlapping.",5.95)


prs.save(OUT)
print("saved",OUT,"slides",len(prs.slides._sldIdLst))
