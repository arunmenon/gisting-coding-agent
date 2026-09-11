import json
figs = json.load(open("paper_figs/figs.json"))

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
.title-wrap{max-width:34ch}
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
.step{flex:1;background:var(--bg2);border:1px solid var(--line);border-radius:16px;padding:26px 24px}
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
"""

def fig(key):
    return figs[key]

S = []
def slide(html): S.append('<section class="slide">%s</section>' % html)

# ---- 1 TITLE ----
slide('''
<div class="title-wrap">
  <div class="eyebrow">Development study &middot; self-hosted coding agent</div>
  <h1>Turning the prompt tax into GPU capacity</h1>
  <p class="lead">Compressing a coding agent&rsquo;s fixed preamble into a handful of learned &ldquo;gist&rdquo; tokens: what it buys, what it costs, and what to fund next.</p>
  <div class="byline">Arun Menon &middot; arumenon@paypal.com</div>
  <div class="stack">Claude Code &rarr; proxy &rarr; vLLM &rarr; Qwen3.8-27B (hybrid attention) &middot; one GPU</div>
</div>''')

# ---- 2 BLUF ----
slide('''
<div class="eyebrow">Bottom line up front</div>
<h2>The answer in four lines</h2>
<div class="grid4" style="margin-top:1.2rem">
  <div class="card copper"><div class="k">The tax</div><div class="v">At every step, the coding agent (Claude Code) re-sends the same fixed preamble to the model: <b>~17.5&ndash;21k</b> tokens, over <b>90% tool schemas</b>, about <b>0.72</b> of a short session.</div></div>
  <div class="card plum"><div class="k">The lever</div><div class="v">Replace it with a few thousand <b>learned tokens</b>. Base model frozen; deployed in a <b>proxy</b>, no client or engine change.</div></div>
  <div class="card"><div class="k">The payoff</div><div class="v"><b>2x the request rate</b> within the latency SLO and <b>+44% peak throughput</b> on the same GPU (tuned server, 3 repeats). A <b>cost lever</b>: a cheaper GPU with gist matched a pricier one per dollar.</div></div>
  <div class="card warn"><div class="k">The caveat</div><div class="v">A <b>development study</b>: the lever is real; the dollar-per-session number is <b>not proven yet</b>.</div></div>
</div>
<p class="caption">You can stop here. The rest is the evidence, the catch, and what it would take to bank the saving.</p>''')

# ---- 3 WHY TCO ----
slide('''
<div class="eyebrow">The cost lens</div>
<h2>Why this is a total-cost question</h2>
<p class="lead" style="margin-bottom:1.4rem">For a self-hosted agent, serving cost is driven by <b>how many tokens the model reads per turn</b>, which caps <b>how many sessions a GPU can carry</b>. Three cost drivers; gisting acts on the first.</p>
<div class="grid3">
  <div class="card" style="border-color:var(--petrol2)"><div class="k" style="color:var(--petrol)">GPU capacity &nbsp;&larr; gisting acts here</div><div class="v">Token-bound. Fewer input tokens per turn &rarr; each session finishes sooner &rarr; more load per GPU before latency degrades. <b>Measured: 2x at the SLO.</b></div></div>
  <div class="card"><div class="k" style="color:var(--ink2)">Engineering</div><div class="v">One-time: build the proxy, the template, and the training loop. The loop is reusable across models.</div></div>
  <div class="card"><div class="k" style="color:var(--ink2)">Risk</div><div class="v">Compressed rules are harder to audit; benefit is model-dependent. Managed, not eliminated.</div></div>
</div>''')

# ---- 4 THE TAX MEASURED ----
slide('''
<div class="eyebrow">The tax, measured</div>
<h2>Most of every turn is machine-readable boilerplate</h2>
<div class="compbar">
  <div class="compseg" style="flex:0 0 78%;background:var(--petrol2)"><div class="cs">Tool schemas</div><div class="ct">~16,000 tokens &middot; &gt;90% of the block</div></div>
  <div class="compseg" style="flex:0 0 9%;background:var(--copper)"><div class="cs" style="font-size:.9rem">Rules</div><div class="ct" style="font-size:.72rem">~1.3k</div></div>
  <div class="compseg" style="flex:0 0 13%;background:#2b3a41"><div class="cs" style="font-size:.9rem">Per-session</div><div class="ct" style="font-size:.72rem">kept raw</div></div>
</div>
<div style="display:flex;gap:48px;flex-wrap:wrap;margin-top:1.4rem">
  <div><div class="bignum copper">17.5&ndash;21k</div><div class="unit">fixed tokens per turn</div></div>
  <div><div class="bignum copper">&gt;90%%</div><div class="unit">is tool schemas, not rules</div></div>
  <div><div class="bignum petrol">0.72</div><div class="unit">of a short session&rsquo;s input</div></div>
</div>
<p class="caption">The coding-agent harness prepends the same block, byte-for-byte, on every model call. Per-session values (paths, git status, date) are split out and kept raw.</p>''')

# ---- 5 THE IDEA ----
slide('''
<div class="eyebrow">The lever</div>
<h2>Teach the model a shorthand for the boilerplate</h2>
<div class="flow">
  <div class="step"><div class="n">01</div><h3>Grow the vocabulary</h3><p>Add a few thousand new &ldquo;gist&rdquo; tokens, seeded from the block they replace.</p></div>
  <div class="arrow">&rarr;</div>
  <div class="step"><div class="n">02</div><h3>Self-distil</h3><p>The model matches its own behaviour (short gist vs. full block). <b style="color:var(--plum)">All base weights frozen</b>; only the new rows train.</p></div>
  <div class="arrow">&rarr;</div>
  <div class="step"><div class="n">03</div><h3>Serve via a proxy</h3><p>The proxy swaps the span for gist tokens. <b>No change to the client or the engine.</b></p></div>
</div>
<p class="caption">The only trained object is a small embedding tensor: cheap to produce, cheap to serve.</p>''')

# ---- 6 PARITY ----
slide('''
<div class="eyebrow">Proof &middot; parity</div>
<h2>The short prompt matched the full prompt</h2>
<div class="ratiorow">
  <div class="chip"><div class="r">2:1</div><div class="s">12 / 12</div></div>
  <div class="chip"><div class="r">4:1</div><div class="s">12 / 12</div></div>
  <div class="chip"><div class="r">8:1</div><div class="s">12 / 12</div></div>
  <div class="chip"><div class="r">16:1</div><div class="s">12 / 12</div></div>
</div>
<p class="lead">Every compression ratio and the full prompt scored a perfect <b>12 / 12</b> on the task suite, while input dropped from <b>~24k</b> to <b>~9&ndash;11k</b> tokens per turn.</p>
<p style="margin-top:1rem"><span class="tag warn">single run &middot; small, partly-reused suite</span></p>''')


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
    o.append('<text x="%d" y="22" fill="#9fb2b6" font-size="13">requests / minute vs concurrent sessions  ·  tuned server, 3 repeats (spread within marker)</text>'%L)
    o.append('</svg>'); return "".join(o)
slide('''
<div class="eyebrow">The payoff (measured)</div>
<h2>The saving shows up as capacity under load</h2>
<div class="figrow">
  <div>%s</div>
  <div>
    <div style="display:flex;gap:34px;flex-wrap:wrap;margin-bottom:.8rem">
      <div><div class="bignum plum">2x</div><div class="unit">request rate within the latency SLO<br>(18 &rarr; 36 req/min, random arrivals)</div></div>
      <div><div class="bignum petrol">+44%%</div><div class="unit">peak throughput, same GPU<br>(42.7 &rarr; 61.3 req/min)</div></div>
    </div>
    <p class="lead">The advantage <b>grows with load</b> (1.12x at 1 session &rarr; 1.65x at 48) and is <b>incremental over prefix caching</b>: 2&ndash;4x larger when caching can't help.</p>
    <div style="margin-top:.8rem"><span class="tag" style="color:#8a9aa0">full prompt</span> <span class="tag" style="color:#c39be0;border-color:#5a3f6e">gist 8:1</span> <span class="tag">H100 NVL 95 GB &middot; 201 runs &middot; 0 failures</span></div>
  </div>
</div>''' % curve())

# ---- 9 WHY CAPACITY NOT SPEED ----
layers="".join('<i class="on"></i>' if k<16 else '<i></i>' for k in range(64))
slide('''
<div class="eyebrow">The catch &middot; architecture</div>
<h2>Why it&rsquo;s capacity, not speed</h2>
<p class="lead">This model uses full attention in only <b>16 of its 64 layers</b>, and the number of sessions it can hold at once is set by a <b>fixed per-session state</b>, not by prompt length. So a shorter prompt does not fit many more sessions; it makes <b>each session finish sooner</b>. The win is throughput under load, not a faster single answer.</p>
<div class="layers">%s</div>
<p class="caption"><span style="color:var(--petrol)">&#9632;</span> full-attention layers &nbsp;&nbsp; <span style="color:#3a4a51">&#9632;</span> linear-attention layers (fixed-size state). Measured: at the resident-session ceiling both arms hold the same number of sessions; the gist just turns them over faster (H200: 85 vs 50 req/min at 100 resident).</p>''' % layers)

# ---- 9b THE COST LEVER (new) ----
slide('''
<div class="eyebrow">The cost lever</div>
<h2>Gisting lets a cheaper GPU match a pricier one</h2>
<div style="display:flex;gap:40px;flex-wrap:wrap;margin:1.2rem 0 1rem">
  <div><div class="bignum" style="color:#8a9aa0">16.2</div><div class="unit">H100 &middot; full prompt</div></div>
  <div><div class="bignum plum">23.2</div><div class="unit">H100 &middot; gist 8:1</div></div>
  <div><div class="bignum petrol">22.5</div><div class="unit">H200 &middot; full prompt</div></div>
  <div><div class="bignum" style="color:#8a9aa0">22.0</div><div class="unit">H200 &middot; gist 8:1</div></div>
</div>
<p class="caption" style="margin-top:0">peak requests per minute, per dollar-hour of GPU rental (spot prices on the day of the run)</p>
<p class="lead" style="margin-top:1.2rem">On the bigger H200 (143 GB), gist&rsquo;s peak gain <b>vanished at normal load</b> (&minus;2%) and appeared only under pressure (3.1x at 128 sessions). On the H100 (95 GB) it was <b>+44%</b>. The benefit is proportional to <b>how memory-constrained the hardware is relative to the prompt</b>.</p>
<p class="caption">Read it as a cost lever, not a speed lever: gist on the cheaper card delivers the expensive card&rsquo;s throughput per dollar. Where prompts don&rsquo;t share prefixes (no cache help), gist&rsquo;s 2&ndash;4x advantage holds on any card.</p>''')

# ---- 10 THE LAB ----
slide('''
<div class="eyebrow">The capability</div>
<h2>We built the lab, not just the result</h2>
<div class="pipe">
  <div class="pnode">Provision GPU</div><div class="parrow">&rarr;</div>
  <div class="pnode">Train</div><div class="parrow">&rarr;</div>
  <div class="pnode">Serve</div><div class="parrow">&rarr;</div>
  <div class="pnode">Evaluate<span class="mono" style="font-size:.72rem;color:var(--ink2);font-weight:400">verify every swap</span></div><div class="parrow">&rarr;</div>
  <div class="pnode">Destroy</div><div class="parrow" style="color:var(--copper)">&#8635;</div>
  <div class="pnode" style="border-style:dashed;color:var(--ink2)">next recipe</div>
</div>
<div class="safety">SPEND-SAFETY &middot; structural &nbsp;&middot;&nbsp; <b>idle watchdog</b> &middot; <b>ledger at creation</b> &middot; <b>sync-before-destroy</b> &middot; <b>global deadline</b></div>
<p class="caption">One detached controller drives every recipe end to end, unattended. Makes the <b>next</b> model cheap to try: the capability outlasts this study.</p>''')

# ---- 11 LEDGER ----
slide('''
<div class="eyebrow">Honest ledger</div>
<h2>What&rsquo;s proven, what isn&rsquo;t</h2>
<div class="grid2" style="margin-top:1rem">
  <div class="card good"><div class="k">Established here</div>
    <ul class="clean good" style="margin:0">
      <li>Equal task scores on our suites, every ratio.</li>
      <li>Half-to-two-thirds fewer tokens read per turn.</li>
      <li><b>2x load within SLO, +44% peak</b> on a tuned server, 3 repeats, 0 failures.</li>
      <li>Incremental over prefix caching (2&ndash;4x without it); mechanism measured.</li>
      <li>Throughput per dollar on two GPU classes; the fix removes the path failure.</li>
    </ul>
  </div>
  <div class="card warn"><div class="k">Not yet</div>
    <ul class="clean warn" style="margin:0">
      <li>Generalisation on unseen, held-out work.</li>
      <li>Per-hardware tuning (the H200 ran an H100-tuned config; one regression at 16 sessions).</li>
      <li>Rare-tool reach (left unscored by harness faults).</li>
      <li>Audit guarantees that compressed rules still bind.</li>
    </ul>
  </div>
</div>
<p class="caption">An independent adversarial review of the whole program was run and folded into the writeup.</p>''')

# ---- 12 THE ASK ----
slide('''
<div class="eyebrow">The ask</div>
<h2>From &ldquo;real lever&rdquo; to a number you can budget</h2>
<div class="grid3" style="margin-top:1rem">
  <div class="card"><div class="k">1 &middot; Validate</div><div class="v">A held-out eval with paired, repeated runs. Answers: is the parity real beyond our own tasks?</div></div>
  <div class="card"><div class="k">2 &middot; Tune per hardware</div><div class="v">Re-tune the server for each GPU class and re-measure; the capacity number is now measured on the H100, and the H200 showed one regression from an H100-tuned config.</div></div>
  <div class="card"><div class="k">3 &middot; Pilot</div><div class="v">A guarded rollout with explicit rule-audit and write-target checks at the serving boundary.</div></div>
</div>
<p class="caption">Bounded effort: a single GPU over days, not a new research program. The capacity number is measured; what remains is proof on work we did not design.</p>''')

# ---- 13 DECISION ----
slide('''
<div class="eyebrow">Decision</div>
<h2>The lever is real and cheap to prototype</h2>
<p class="big-verdict">The capacity number is measured. Fund the held-out validation and a guarded pilot.</p>
<p class="lead" style="margin-top:1.3rem">The tooling exists, the risk is contained, and the upside is measured: <b>2x the load within SLO on the same GPU</b>, or the same throughput per dollar from a cheaper GPU. What&rsquo;s missing is proof on unseen work, and that is days of work away, not months.</p>
<div class="stack" style="margin-top:1.6rem">GitHub: arunmenon/gisting-coding-agent &middot; weights &amp; data on Hugging Face (private)</div>''')

# ---- APPENDIX: THE FAILURE ----
slide('''
<div class="eyebrow">Appendix &middot; the failure we caught</div>
<h2>The failure that mattered, and the fix</h2>
<div class="ba">
  <div><span class="tag warn big">BEFORE</span></div>
  <div class="baflow"><span class="pill plum">gist: rules + &hellip;/&lt;session-id&gt;/</span><span class="parrow">&rarr;</span><span class="pill bad">writes to an invented directory &#10007;</span></div>
  <div><span class="tag good big">AFTER</span></div>
  <div class="baflow"><span class="pill plum">gist: rules</span><span class="plus">+</span><span class="pill">raw: session path, date, model</span><span class="parrow">&rarr;</span><span class="pill ok">writes to the right place &#10003;</span></div>
</div>
<p class="lead" style="margin-top:1.5rem">Keeping session-specific values <b>raw</b> restored the score <b style="color:var(--good)">11/16 &rarr; 16/16</b> at 8:1.</p>
<p class="caption">The productionization gotcha every deployment will hit, and evidence we were looking hard, not cherry-picking.</p>''')

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

html = ('<title>Gisting: the capacity lever</title>\n'
 '<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
 '<link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,600&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500;600&display=swap" rel="stylesheet">'
 '<style>'+CSS+'</style>\n'
 '<div class="hint">&larr; &rarr; to navigate</div>'
 '<div class="deck">'+''.join(S)+'</div>'
 '<div class="rail"><div class="count" id="count">01 / 13</div><div class="dots" id="dots"></div></div>'
 '<script>'+JS+'</script>')
open("gisting-cto-deck.html","w").write(html)
print("wrote gisting-cto-deck.html", len(html)//1024, "KB | slides", len(S))
