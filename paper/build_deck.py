import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
figs = json.load(open(HERE / "paper_figs/figs.json"))

CSS = """
:root{
  --bg:#0e1417; --bg2:#141d21; --panel:#18232800; --ink:#eef3f3; --ink2:#9fb2b6;
  --line:#25333a; --petrol:#3fb0c6; --petrol2:#1f5f6e; --plum:#c39be0; --copper:#e08a4c;
  --good:#57c08a; --warn:#e3b24c; --card:#fbfbf9;
  --serif:"Fraunces",Georgia,serif; --sans:"IBM Plex Sans",system-ui,sans-serif; --mono:"IBM Plex Mono",ui-monospace,monospace;
}
*{box-sizing:border-box}
html{scroll-snap-type:y mandatory;scroll-behavior:smooth}
@media (prefers-reduced-motion:reduce){html{scroll-behavior:auto}}
body{margin:0;background:var(--bg);color:var(--ink);font-family:var(--sans);font-size:17px;line-height:1.5;-webkit-font-smoothing:antialiased}
.deck{width:100%}
.slide{min-height:100vh;scroll-snap-align:start;display:flex;flex-direction:column;justify-content:center;
  padding:clamp(30px,6vh,70px) clamp(28px,7vw,120px) clamp(60px,9vh,96px);position:relative;border-bottom:1px solid var(--line);overflow:hidden}
.eyebrow{font-family:var(--mono);font-size:.74rem;letter-spacing:.22em;text-transform:uppercase;color:var(--petrol);margin-bottom:.9rem}
h1{font-family:var(--serif);font-weight:600;font-size:clamp(2rem,4.4vw,3.5rem);line-height:1.06;margin:.1em 0;letter-spacing:-.01em;text-wrap:balance}
h2{font-family:var(--serif);font-weight:600;font-size:clamp(1.7rem,3.8vw,2.9rem);line-height:1.08;margin:0 0 .5em;letter-spacing:-.01em;text-wrap:balance;max-width:20ch}
.lead{color:var(--ink2);font-size:clamp(1.02rem,1.5vw,1.28rem);max-width:60ch;line-height:1.5}
.sub{color:var(--ink2);max-width:64ch;font-size:1.05rem}
p{margin:.5em 0}
b,strong{color:var(--ink);font-weight:600}
.mono{font-family:var(--mono)}
.tag{display:inline-block;font-family:var(--mono);font-size:.72rem;letter-spacing:.04em;padding:4px 10px;border-radius:999px;border:1px solid var(--line);color:var(--ink2)}
.tag.warn{color:var(--warn);border-color:#5a4a24}
.tag.good{color:var(--good);border-color:#2c5040}
/* title */
.title-wrap{max-width:46ch}
.byline{font-family:var(--mono);color:var(--ink2);font-size:.9rem;margin-top:2.2rem}
.stack{font-family:var(--mono);color:var(--petrol);font-size:.8rem;letter-spacing:.05em;margin-top:.5rem}
/* grids */
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:26px}
.grid4{display:grid;grid-template-columns:repeat(4,1fr);gap:20px}
.grid3{display:grid;grid-template-columns:repeat(3,1fr);gap:22px}
@media(max-width:860px){.grid2,.grid4,.grid3{grid-template-columns:1fr}}
/* cards */
.card{background:var(--bg2);border:1px solid var(--line);border-radius:14px;padding:22px 22px}
.card .k{font-family:var(--mono);font-size:.72rem;letter-spacing:.12em;text-transform:uppercase;color:var(--petrol);margin-bottom:.55rem}
.card.copper .k{color:var(--copper)} .card.plum .k{color:var(--plum)} .card.good .k{color:var(--good)} .card.warn .k{color:var(--warn)}
.card .v{font-size:1.02rem;color:var(--ink);line-height:1.45}
.card .v b{color:#fff}
.bignum{font-family:var(--mono);font-weight:600;font-size:clamp(2rem,4.4vw,3.2rem);line-height:1;letter-spacing:-.02em}
.bignum.petrol{color:var(--petrol)} .bignum.copper{color:var(--copper)} .bignum.plum{color:var(--plum)} .bignum.good{color:var(--good)}
.unit{font-family:var(--mono);font-size:.8rem;color:var(--ink2);margin-top:.5rem;letter-spacing:.02em}
/* figure card (paper diagrams are light-bg) */
.figcard{background:var(--card);border-radius:14px;padding:14px;border:1px solid var(--line)}
.figcard img{display:block;width:100%;height:auto;border-radius:6px}
.figrow{display:grid;grid-template-columns:1.25fr .9fr;gap:34px;align-items:center}
@media(max-width:900px){.figrow{grid-template-columns:1fr}}
ul.clean{list-style:none;padding:0;margin:.4rem 0}
ul.clean li{padding-left:1.3em;position:relative;margin:.6rem 0;color:var(--ink2)}
ul.clean li b{color:var(--ink)}
ul.clean li::before{content:"";position:absolute;left:0;top:.62em;width:8px;height:8px;border-radius:2px;background:var(--petrol)}
ul.clean.plum li::before{background:var(--plum)} ul.clean.copper li::before{background:var(--copper)}
ul.clean.good li::before{background:var(--good)} ul.clean.warn li::before{background:var(--warn)}
.ratiorow{display:flex;gap:14px;flex-wrap:wrap;margin:1.2rem 0}
.chip{font-family:var(--mono);border:1px solid var(--petrol2);border-radius:10px;padding:12px 18px;text-align:center;background:var(--bg2)}
.chip .r{color:var(--petrol);font-size:1.15rem;font-weight:600}
.chip .s{color:var(--good);font-size:.85rem;margin-top:4px}
.caption{color:var(--ink2);font-size:.92rem;max-width:60ch;margin-top:1rem}
.big-verdict{font-family:var(--serif);font-size:clamp(1.4rem,2.6vw,2.1rem);line-height:1.25;max-width:24ch;color:#fff}
/* layer motif */
.layers{display:grid;grid-template-columns:repeat(16,1fr);gap:4px;max-width:520px;margin:1rem 0}
.layers i{aspect-ratio:1;border-radius:3px;background:#243036;display:block}
.layers i.on{background:var(--petrol)}
/* footer rail */
.rail{position:fixed;left:0;right:0;bottom:0;height:44px;display:flex;align-items:center;justify-content:space-between;
  padding:0 clamp(20px,5vw,60px);font-family:var(--mono);font-size:.74rem;color:var(--ink2);
  background:linear-gradient(0deg,rgba(14,20,23,.95),rgba(14,20,23,.0));z-index:20;pointer-events:none}
.dots{display:flex;gap:7px;pointer-events:auto}
.dots b{width:8px;height:8px;border-radius:50%;background:#2b3a41;display:block;cursor:pointer;transition:background .2s,transform .2s}
.dots b.on{background:var(--petrol);transform:scale(1.35)}
.count b{color:var(--petrol)}
svg text{font-family:var(--mono)}
.hint{position:fixed;right:16px;top:14px;font-family:var(--mono);font-size:.7rem;color:var(--ink2);opacity:.6;z-index:20}
/* slide-native visuals (presentation scale) */
.compbar{display:flex;height:96px;border-radius:14px;overflow:hidden;margin:1.6rem 0 1.2rem;border:1px solid var(--line)}
.compseg{display:flex;flex-direction:column;justify-content:center;padding:0 22px;color:#fff}
.compseg .cs{font-weight:600;font-size:1.05rem} .compseg .ct{font-family:var(--mono);font-size:.82rem;opacity:.85;margin-top:3px}
.flow{display:flex;align-items:stretch;gap:6px;margin:1.6rem 0 1.1rem}
.step{flex:1;min-width:0;background:var(--bg2);border:1px solid var(--line);border-radius:16px;padding:26px 24px}
.step .n{font-family:var(--mono);color:var(--petrol);font-size:.82rem;letter-spacing:.14em}
.step h3{font-family:var(--serif);font-weight:600;font-size:1.4rem;margin:.4rem 0 .5rem;color:#fff}
.step p{color:var(--ink2);font-size:1.02rem;line-height:1.4;margin:0}
.arrow{display:flex;align-items:center;color:var(--petrol);font-size:1.9rem;font-weight:600}
.ba{display:grid;grid-template-columns:auto 1fr;gap:22px 22px;align-items:center;margin:1.6rem 0 1rem}
.baflow{display:flex;align-items:center;gap:14px;flex-wrap:wrap}
.pill{background:var(--bg2);border:1px solid var(--line);border-radius:12px;padding:16px 20px;font-family:var(--mono);font-size:1.02rem;color:var(--ink)}
.pill.plum{border-color:#5a3f6e;color:var(--plum)} .pill.bad{border-color:#6e3a3a;color:#e79191} .pill.ok{border-color:#2c5040;color:var(--good)}
.plus{color:var(--ink2);font-size:1.3rem} .parrow{color:var(--petrol);font-size:1.7rem;font-weight:600}
.tag.big{font-size:.9rem;padding:8px 16px}
.pipe{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin:1.6rem 0 1.2rem}
.pnode{background:var(--bg2);border:1px solid var(--line);border-radius:14px;padding:20px 22px;font-weight:600;font-size:1.08rem;text-align:center;min-width:120px}
.pnode span{display:block}
.safety{background:rgba(224,138,76,.09);border:1px solid #5a4a2a;border-radius:14px;padding:16px 20px;font-family:var(--mono);font-size:.92rem;color:var(--ink2);margin-top:.4rem}
.safety b{color:var(--copper);font-weight:600}
.eqline{display:flex;flex-wrap:wrap;align-items:center;gap:12px;font-family:var(--mono);font-size:clamp(1rem,1.8vw,1.3rem);margin:.6rem 0 1.4rem;color:var(--ink2)}
.eqline span{border:1px solid var(--line);border-radius:10px;padding:8px 14px;color:var(--ink);background:var(--bg2)}
.eqline span.hot{border-color:#5a3f6e;color:var(--plum)}
.eqline i{font-style:normal;color:var(--petrol)}
.term{font-family:var(--mono);font-size:.78rem;color:var(--ink2);margin:-.2rem 0 .6rem}
"""

def fig(key):
    return figs[key]

S = []
def slide(html): S.append('<section class="slide">%s</section>' % html)

# ---- 8 PAYOFF (SVG curve, measured) ----
def curve():
    cs=["1","2","4","8","16","32","48","64"]
    full=[13.1,22.7,36.9,34.7,42.7,42.7,32.0,29.3]; gist=[14.7,25.3,42.7,48.0,59.3,61.3,52.7,41.3]
    W,H=680,340; L,B,T=54,54,40; ymax=70; pw=W-L-24; ph=H-B-T
    X=lambda i: L+i*pw/(len(cs)-1); Y=lambda v: H-B-v/ymax*ph
    o=['<svg viewBox="0 0 %d %d" width="100%%" role="img" aria-label="Throughput versus concurrent sessions, full prompt versus gist">'%(W,H)]
    o.append('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="#2b3a41" stroke-width="1.5"/>'%(L,H-B,W-16,H-B))
    for yv in (14,28,42,56,70): o.append('<text x="%d" y="%.1f" fill="#6f8085" font-size="11" text-anchor="end">%d</text>'%(L-8,Y(yv)+4,yv))
    for name,vals,col in (("full prompt",full,"#8a9aa0"),("gist 8:1",gist,"#c39be0")):
        pts=" ".join("%.1f,%.1f"%(X(i),Y(v)) for i,v in enumerate(vals))
        o.append('<polyline points="%s" fill="none" stroke="%s" stroke-width="4" stroke-linejoin="round"/>'%(pts,col))
        for i,v in enumerate(vals): o.append('<circle cx="%.1f" cy="%.1f" r="5" fill="%s"/>'%(X(i),Y(v),col))
    o.append('<text x="%.1f" y="%.1f" fill="#c39be0" font-size="14" font-weight="600">61.3  (+44%%)</text>'%(X(5)+10,Y(61.3)-10))
    o.append('<text x="%.1f" y="%.1f" fill="#cfe0e3" font-size="13">42.7</text>'%(X(4)-14,Y(42.7)+22))
    o.append('<text x="%.1f" y="%.1f" fill="#e79191" font-size="12">full collapses (KV 100%%)</text>'%(X(6)-70,Y(32.0)+28))
    for i,l in enumerate(cs): o.append('<text x="%.1f" y="%d" fill="#9fb2b6" font-size="13" text-anchor="middle">%s</text>'%(X(i),H-B+22,l))
    o.append('<text x="%d" y="22" fill="#9fb2b6" font-size="13">requests / minute vs concurrent sessions  ·  mean of 3 repeats</text>'%L)
    o.append('</svg>'); return "".join(o)

# ---- 1 TITLE ----
slide('''
<div class="title-wrap">
  <div class="eyebrow">Lattice &middot; cost optimization &middot; new pillar</div>
  <h1>Gisting: cutting the prompt tax every agent call pays</h1>
  <p class="lead">A learned shorthand for the fixed preamble a coding-agent harness re-sends on every model call. Proven on one harness and model pairing, and built to carry to the others.</p>
  <div class="byline">Arun Menon &middot; arumenon@paypal.com</div>
  <div class="stack">First pairing: Claude Code &rarr; proxy &rarr; vLLM &rarr; Qwen3.8-27B (open weights, self-hosted)</div>
</div>''')

# ---- 2 BLUF ----
slide('''
<div class="eyebrow">Bottom line up front</div>
<h2>The answer in four lines</h2>
<div class="grid4" style="margin-top:1.2rem">
  <div class="card"><div class="k">Where it fits</div><div class="v">A fourth Lattice lever. Routing and distillation cut <b>cost per token</b>; the meta-harness shapes <b>calls</b>. Gisting cuts the <b>fixed tokens</b> every call carries.</div></div>
  <div class="card plum"><div class="k">What we showed</div><div class="v">On Claude Code with Qwen: task scores held at every compression ratio, input per turn <b>more than halved</b>, and on an H100 <b>2x the request rate</b> within the latency target, <b>+44% peak throughput</b>.</div></div>
  <div class="card warn"><div class="k">What it isn&rsquo;t yet</div><div class="v">One pairing, our own task suite, short replay windows. <b>Savings per task are not proven</b>, and the mechanism is still open.</div></div>
  <div class="card good"><div class="k">The ask</div><div class="v">Take the recipe to a <b>second harness and model pairing</b> through the meta-harness, validate on held-out work, then a guarded pilot.</div></div>
</div>''')

# ---- 3 LATTICE MAP ----
slide('''
<div class="eyebrow">Where gisting sits in Lattice</div>
<h2>Four levers on one cost equation</h2>
<div class="eqline"><span>cost per task</span><i>=</i><span>calls</span><i>&times;</i><span class="hot">tokens per call</span><i>&times;</i><span>cost per token</span></div>
<div class="grid4">
  <div class="card"><div class="k">Lattice meta-harness</div><div class="term">calls &middot; where they land</div><div class="v">One adapter from any harness to any model. The control point for how calls are made and which model serves them.</div></div>
  <div class="card plum" style="border-color:#5a3f6e"><div class="k">Gisting &middot; this pillar</div><div class="term">fixed tokens per call</div><div class="v">Learned shorthand for the preamble every call repeats: tool schemas and rules.</div></div>
  <div class="card"><div class="k">Adaptive routing</div><div class="term">cost per token</div><div class="v">Sends each request to the cheapest model that can handle it.</div></div>
  <div class="card"><div class="k">Model distillation</div><div class="term">cost per token</div><div class="v">Smaller student models for the work that allows it.</div></div>
</div>
<p class="caption">The levers multiply rather than compete. A distilled model reached through the router still reads the full preamble on every call, unless it is gisted.</p>''')

# ---- 4 THE TAX ----
slide('''
<div class="eyebrow">The tax</div>
<h2>Most of every call is the same boilerplate</h2>
<div class="compbar">
  <div class="compseg" style="flex:0 0 78%;background:var(--petrol2)"><div class="cs">Tool schemas</div><div class="ct">~16,000 tokens &middot; &gt;90% of the block</div></div>
  <div class="compseg" style="flex:0 0 9%;background:var(--copper)"><div class="cs" style="font-size:.9rem">Rules</div><div class="ct" style="font-size:.72rem">~1.3k</div></div>
  <div class="compseg" style="flex:0 0 13%;background:#2b3a41"><div class="cs" style="font-size:.9rem">Per-session</div><div class="ct" style="font-size:.72rem">kept raw</div></div>
</div>
<div style="display:flex;gap:48px;flex-wrap:wrap;margin-top:1.4rem">
  <div><div class="bignum copper">17.5&ndash;21k</div><div class="unit">fixed tokens on every call</div></div>
  <div><div class="bignum copper">&gt;90%</div><div class="unit">is tool schemas, not rules</div></div>
  <div><div class="bignum petrol">0.72</div><div class="unit">of a short session&rsquo;s input</div></div>
</div>
<p class="caption">Measured on Claude Code with the Qwen tokenizer. Any harness that exposes tools pays a version of this, but its size and makeup differ, so every new pairing starts with the same span study.</p>''')

# ---- 5 THE RECIPE ----
slide('''
<div class="eyebrow">The recipe</div>
<h2>Four steps, most of them reusable</h2>
<div class="flow">
  <div class="step" style="border-color:var(--copper)"><div class="n" style="color:var(--copper)">00 &middot; per pairing</div><h3>Study the span</h3><p>Measure what that harness re-sends, what is fixed and what is per-session, and its share of each call.</p></div>
  <div class="arrow">&rarr;</div>
  <div class="step"><div class="n">01</div><h3>Grow the vocabulary</h3><p>Add a few thousand new &ldquo;gist&rdquo; tokens, seeded from the block they replace.</p></div>
  <div class="arrow">&rarr;</div>
  <div class="step"><div class="n">02</div><h3>Self-distil</h3><p>The model learns to behave the same on the short form. <b style="color:var(--plum)">Base weights frozen</b>; only the new rows train.</p></div>
  <div class="arrow">&rarr;</div>
  <div class="step"><div class="n">03</div><h3>Swap in a proxy</h3><p>The proxy replaces the preamble with gist tokens. <b>No change to the harness or the engine.</b></p></div>
</div>
<div class="grid2" style="margin-top:.4rem">
  <div class="card good"><div class="k">Portable across pairings</div><div class="v">Training loop, proxy, evaluation harness, and the automated GPU lab that runs them.</div></div>
  <div class="card copper"><div class="k">Redone per pairing</div><div class="v">The span study for that harness and its tokenizer, then new rows trained for that model. Needs <b>open weights we host</b>; closed models get provider prompt caching instead.</div></div>
</div>''')

# ---- 6 PROOF ----
slide('''
<div class="eyebrow">Proof on the first pairing &middot; Claude Code &times; Qwen3.8</div>
<h2>The short prompt did the same work</h2>
<div class="ratiorow">
  <div class="chip"><div class="r">2:1</div><div class="s">12 / 12</div></div>
  <div class="chip"><div class="r">4:1</div><div class="s">12 / 12</div></div>
  <div class="chip"><div class="r">8:1</div><div class="s">12 / 12</div></div>
  <div class="chip"><div class="r">16:1</div><div class="s">12 / 12</div></div>
</div>
<p class="lead">Every compression ratio matched the full prompt on the task suite, while input per turn fell from <b>~24k</b> to <b>~9&ndash;11k</b> tokens. We run at <b>8:1</b>: 16:1 bought only about 60% of the serving gain for more risk.</p>
<p class="lead" style="margin-top:.8rem">The one failure that mattered: session values such as the working path must stay raw. Fixing that took a harder suite from <b>11/16 to 16/16</b>.</p>
<p style="margin-top:1rem"><span class="tag warn">single runs &middot; small, partly reused suites</span></p>''')

# ---- 7 PAYOFF ----
slide('''
<div class="eyebrow">The payoff</div>
<h2>More work from the same GPU</h2>
<div class="figrow">
  <div>%s</div>
  <div>
    <div style="display:flex;gap:34px;flex-wrap:wrap;margin-bottom:.8rem">
      <div><div class="bignum plum">2x</div><div class="unit">request rate within the latency target<br>(18 &rarr; 36 req/min, random arrivals)</div></div>
      <div><div class="bignum petrol">+44%%</div><div class="unit">peak throughput, same H100<br>(42.7 &rarr; 61.3 req/min)</div></div>
    </div>
    <p class="lead">It is a <b>capacity</b> lever, not a speed lever: a single reply is barely faster. The gain comes on top of prefix caching.</p>
    <p class="caption">Short replay windows on one GPU class. On a larger H200 the peak gain was near zero, and the cost comparison between the two cards came out roughly even (appendix).</p>
  </div>
</div>''' % curve())

# ---- 8 STACKING ----
slide('''
<div class="eyebrow">How it compounds with Lattice</div>
<h2>Built to plug into the other pillars</h2>
<div class="grid3" style="margin-top:1rem">
  <div class="card"><div class="k">Meta-harness</div><div class="v">The adapter already sits between harness and model. The gist swap is a proxy step, so it can live there and serve <b>every harness routed through it</b>.</div></div>
  <div class="card"><div class="k">Distillation</div><div class="v">A student model still reads the full preamble on every call. The same recipe trains rows for the student: <b>smaller model, shorter prompt</b>.</div></div>
  <div class="card"><div class="k">Adaptive routing</div><div class="v">A gisted endpoint becomes a cheaper target for the router, with the full-prompt path kept as a <b>fallback</b>.</div></div>
</div>
<p style="margin-top:1.2rem"><span class="tag warn">design fit &middot; not yet measured</span></p>''')

# ---- 9 JETSTREAM ----
slide('''
<div class="eyebrow">Where it lands &middot; Jetstream PDLC</div>
<h2>Coding agents on many harnesses, many models</h2>
<div class="grid3" style="margin-top:1rem">
  <div class="card plum" style="border-color:#5a3f6e"><div class="k">Inner loop &middot; ticket to PR</div><div class="v"><b>Best fit.</b> Many short agent steps, each re-sending the same tool preamble. The closest match to what we tested.</div></div>
  <div class="card"><div class="k">Outer loop &middot; vision, PRD, HLD</div><div class="v"><b>Smaller fit.</b> Fewer, document-heavy calls, where the fixed preamble is a smaller share of each call.</div></div>
  <div class="card"><div class="k">Memory</div><div class="v"><b>Complementary.</b> Memory is session-specific, so it stays raw; gisting covers only what never changes. That boundary is the lesson from our one real failure.</div></div>
</div>
<p class="caption">Applies to Jetstream traffic that reaches an open-weights model we host through the meta-harness. Calls to closed models keep using provider prompt caching.</p>''')

# ---- 10 LEDGER ----
slide('''
<div class="eyebrow">Honest ledger</div>
<h2>What&rsquo;s proven, what isn&rsquo;t</h2>
<div class="grid2" style="margin-top:1rem">
  <div class="card good"><div class="k">Established</div>
    <ul class="clean good" style="margin:0">
      <li>Equal task scores at every ratio on our suites.</li>
      <li>Half to two thirds fewer tokens read per turn.</li>
      <li>H100 replay: <b>2x rate within the latency target, +44% peak</b>.</li>
      <li>A reusable, spend-safe lab that runs the recipe end to end.</li>
    </ul>
  </div>
  <div class="card warn"><div class="k">Not yet</div>
    <ul class="clean warn" style="margin:0">
      <li>A second harness and model pairing, including its span study.</li>
      <li>Quality on held-out work, and at production load.</li>
      <li>Savings per task, and why the gain happens. An external review withdrew our first explanation.</li>
      <li>Audit that compressed rules still bind.</li>
    </ul>
  </div>
</div>''')

# ---- 11 THE LAB ----
slide('''
<div class="eyebrow">The capability</div>
<h2>The next pairing is cheap to try</h2>
<div class="pipe">
  <div class="pnode">Provision GPU</div><div class="parrow">&rarr;</div>
  <div class="pnode">Train</div><div class="parrow">&rarr;</div>
  <div class="pnode">Serve</div><div class="parrow">&rarr;</div>
  <div class="pnode">Evaluate<span class="mono" style="font-size:.72rem;color:var(--ink2);font-weight:400">verify every swap</span></div><div class="parrow">&rarr;</div>
  <div class="pnode">Destroy</div><div class="parrow" style="color:var(--copper)">&#8635;</div>
  <div class="pnode" style="border-style:dashed;color:var(--ink2)">next pairing</div>
</div>
<div class="safety">SPEND-SAFETY &middot; structural &nbsp;&middot;&nbsp; <b>idle watchdog</b> &middot; <b>ledger at creation</b> &middot; <b>sync-before-destroy</b> &middot; <b>global deadline</b></div>
<p class="caption">One controller drives a recipe end to end, unattended. Swapping in a new harness or model changes the inputs, not the machinery.</p>''')

# ---- 12 ASK + DECISION ----
slide('''
<div class="eyebrow">The ask</div>
<h2>Make gisting a Lattice pillar</h2>
<div class="grid3" style="margin-top:1rem">
  <div class="card plum" style="border-color:#5a3f6e"><div class="k">1 &middot; Second pairing</div><div class="v">A Jetstream inner-loop harness on an open-weights model, through the meta-harness, starting with its span study. Proves the recipe carries.</div></div>
  <div class="card"><div class="k">2 &middot; Validate</div><div class="v">Held-out tasks, repeated runs, and quality checked at production load.</div></div>
  <div class="card"><div class="k">3 &middot; Guarded pilot</div><div class="v">Inner loop, behind the meta-harness, with an automatic fallback to the full prompt.</div></div>
</div>
<p class="big-verdict" style="margin-top:1.6rem">The lever is real on one pairing. The next step is showing it travels.</p>
<div class="stack" style="margin-top:1.2rem">White paper, code and results: GitHub arunmenon/gisting-coding-agent &middot; weights and data on Hugging Face (private)</div>''')

# ---- APPENDIX A: CORRECTION ----
layers="".join('<i class="on"></i>' if k<16 else '<i></i>' for k in range(64))
slide('''
<div class="eyebrow">Appendix A &middot; a correction we made</div>
<h2>Our first explanation of the gain was wrong</h2>
<p class="lead">External review found a 100-connection limit in our own load generator, and that limit, not the GPU, produced the number our explanation rested on. A follow-up with the limit removed confirmed it. We withdrew the explanation; the throughput figures measured below that limit stand.</p>
<div class="layers">%s</div>
<p class="caption" style="max-width:90ch">The model mixes 16 full-attention layers with 48 linear-attention layers, which is why its behaviour under load differs from a standard transformer. Why the gist helps on it is still open.</p>''' % layers)

# ---- APPENDIX B: COST ----
slide('''
<div class="eyebrow">Appendix B &middot; cost per rental dollar</div>
<h2>Roughly even across the two cards</h2>
<div style="display:flex;gap:40px;flex-wrap:wrap;margin:1.2rem 0 1rem">
  <div><div class="bignum" style="color:#8a9aa0">16.16</div><div class="unit">H100 &middot; full prompt</div></div>
  <div><div class="bignum plum">23.23</div><div class="unit">H100 &middot; gist 8:1</div></div>
  <div><div class="bignum petrol">23.38</div><div class="unit">H200 &middot; full prompt</div></div>
  <div><div class="bignum" style="color:#8a9aa0">22.83</div><div class="unit">H200 &middot; gist 8:1</div></div>
</div>
<p class="caption" style="margin-top:0">peak replay requests per minute per dollar-hour, quoted prices: H100 $2.64/h, H200 $3.65/h</p>
<p class="lead" style="margin-top:1.2rem">On the H100 the gist lifts output per dollar by about 44%. The H100 with the gist lands level with the H200 without it, so this does <b>not</b> yet show a cheaper card can replace a pricier one.</p>''')

# ---- APPENDIX C: THE FAILURE ----
slide('''
<div class="eyebrow">Appendix C &middot; the failure we caught</div>
<h2>What to keep out of the gist</h2>
<div class="ba">
  <div><span class="tag warn big">BEFORE</span></div>
  <div class="baflow"><span class="pill plum">gist: rules + &hellip;/&lt;session-id&gt;/</span><span class="parrow">&rarr;</span><span class="pill bad">writes to an invented directory &#10007;</span></div>
  <div><span class="tag good big">AFTER</span></div>
  <div class="baflow"><span class="pill plum">gist: rules</span><span class="plus">+</span><span class="pill">raw: session path, date, model</span><span class="parrow">&rarr;</span><span class="pill ok">writes to the right place &#10003;</span></div>
</div>
<p class="lead" style="margin-top:1.5rem">Keeping session-specific values <b>raw</b> restored the score <b style="color:var(--good)">11/16 &rarr; 16/16</b> at 8:1.</p>
<p class="caption">Every new pairing will hit this boundary. It is also why memory and gisting are complementary rather than overlapping.</p>''')


# nav
JS = """
const slides=[...document.querySelectorAll('.slide')];
const dots=document.getElementById('dots'), count=document.getElementById('count');
slides.forEach((s,i)=>{const b=document.createElement('b');b.onclick=()=>slides[i].scrollIntoView();dots.appendChild(b);});
const dotEls=[...dots.children];
let cur=0;
const io=new IntersectionObserver((es)=>{es.forEach(e=>{if(e.isIntersecting){cur=slides.indexOf(e.target);
  dotEls.forEach((d,i)=>d.classList.toggle('on',i===cur));
  count.innerHTML='<b>'+String(cur+1).padStart(2,'0')+'</b> / '+String(slides.length).padStart(2,'0');}})},{threshold:.55});
slides.forEach(s=>io.observe(s));
function go(d){const n=Math.max(0,Math.min(slides.length-1,cur+d));slides[n].scrollIntoView();}
addEventListener('keydown',e=>{
  if(['ArrowDown','ArrowRight','PageDown',' '].includes(e.key)){e.preventDefault();go(1);}
  if(['ArrowUp','ArrowLeft','PageUp'].includes(e.key)){e.preventDefault();go(-1);}
  if(e.key==='Home'){e.preventDefault();slides[0].scrollIntoView();}
  if(e.key==='End'){e.preventDefault();slides[slides.length-1].scrollIntoView();}
});
"""

html = ('<title>Gisting for Lattice</title>\n'
 '<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
 '<link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,600&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500;600&display=swap" rel="stylesheet">'
 '<style>'+CSS+'</style>\n'
 '<div class="hint">&larr; &rarr; to navigate</div>'
 '<div class="deck">'+''.join(S)+'</div>'
 '<div class="rail"><div class="count" id="count">01 / 15</div><div class="dots" id="dots"></div></div>'
 '<script>'+JS+'</script>')
(HERE / "gisting-cto-deck.html").write_text(html)
(HERE.parent / "Gisting-CTO-deck.html").write_text(html)
print("wrote gisting-cto-deck.html", len(html)//1024, "KB | slides", len(S))
