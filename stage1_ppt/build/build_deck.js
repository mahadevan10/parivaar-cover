// Builds the Stage 1 pitch deck: node build_deck.js
const path = require("path");
const React = require("react");
const ReactDOMServer = require("react-dom/server");
const sharp = require("sharp");
const pptxgen = require("pptxgenjs");
const lu = require("react-icons/lu");
const { applyTheme } = require("./apply_theme.js");

const OUT = path.join(__dirname, "..", "Parivaar_Cover_Team_Prometheus.pptx");

const THEME = {
  name: "Parivaar Cover",
  headFontFace: "Arial",
  bodyFontFace: "Arial",
  colors: {
    dk1: "13213F", // body text
    lt1: "FFFFFF",
    dk2: "002E6E", // Paytm navy
    lt2: "EAF6FC", // light sky tint for cards
    accent1: "00BAF2", // Paytm sky, fills only
    accent2: "FFB020", // amber highlight
    accent3: "1FA971", // green for ticks
    accent4: "64748B", // muted slate text
    accent5: "0A7AB8", // deep sky for text accents on white
    accent6: "B8E9FB", // pale sky
    hlink: "0A7AB8",
    folHlink: "002E6E",
  },
};
const HEX = THEME.colors;

const W = 13.333;
const MX = 0.6; // side margin
const CW = W - 2 * MX; // content width

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE";
pres.title = "Parivaar Cover: Team Prometheus";
pres.author = "Team Prometheus";
pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
const C = pres.SchemeColor;

// ---------- helpers ----------

async function icon(name, hex, size = 384) {
  let svg = ReactDOMServer.renderToStaticMarkup(React.createElement(lu[name], { size }));
  svg = svg.replace(/currentColor/g, "#" + hex);
  const buf = await sharp(Buffer.from(svg)).resize(size, size).png().toBuffer();
  return "image/png;base64," + buf.toString("base64");
}

const shadow = () => ({ type: "outer", color: "0B1B3A", blur: 8, offset: 2, angle: 90, opacity: 0.12 });

function card(slide, x, y, w, h, opts = {}) {
  slide.addShape(pres.shapes.ROUNDED_RECTANGLE, {
    x, y, w, h,
    rectRadius: opts.radius ?? 0.12,
    fill: opts.fill ?? { color: C.background2 },
    line: opts.line ?? { type: "none" },
    shadow: opts.shadow ? shadow() : undefined,
    objectName: opts.name,
  });
}

function text(slide, str, x, y, w, h, opts = {}) {
  slide.addText(str, { x, y, w, h, margin: 0, valign: "top", isTextBox: true, color: C.text1, fontSize: 14, ...opts });
}

function iconCircle(slide, img, x, y, d, fill = C.accent1, name) {
  slide.addShape(pres.shapes.OVAL, { x, y, w: d, h: d, fill: { color: fill }, line: { type: "none" }, objectName: name });
  const pad = d * 0.24;
  slide.addImage({ data: img, x: x + pad, y: y + pad, w: d - 2 * pad, h: d - 2 * pad });
}

function avatar(slide, initial, x, y, d, fill, fontSize) {
  slide.addText(initial, {
    shape: pres.shapes.OVAL, x, y, w: d, h: d, margin: 0,
    fill: { color: fill }, line: { color: C.background1, width: 1.5 },
    align: "center", valign: "middle", bold: true, color: C.text2, fontSize, isTextBox: true,
  });
}

const FAMILY = [
  { i: "M", name: "Mohan", age: 64, fill: C.accent2, note: "diabetic" },
  { i: "L", name: "Lata", age: 60, fill: C.accent2 },
  { i: "R", name: "Rahul", age: 36, fill: C.accent1 },
  { i: "S", name: "Sneha", age: 33, fill: C.accent1 },
  { i: "A", name: "Aarav", age: 6, fill: C.accent6 },
];
const fam = (i) => FAMILY.find((m) => m.i === i);

// ---------- layouts ----------

pres.defineSlideMaster({
  title: "TITLE_DARK",
  background: { color: C.text2 },
  objects: [
    { placeholder: { options: { name: "kicker", type: "body", x: 0.7, y: 1.55, w: 7.0, h: 0.4, fontSize: 13, bold: true, color: C.accent1, charSpacing: 1, margin: 0, valign: "top", align: "left" }, text: "" } },
    { placeholder: { options: { name: "title", type: "title", x: 0.7, y: 2.05, w: 7.0, h: 1.2, fontSize: 60, bold: true, color: C.background1, margin: 0, valign: "top", align: "left" }, text: "" } },
    { placeholder: { options: { name: "subtitle", type: "body", x: 0.7, y: 3.35, w: 6.4, h: 1.2, fontSize: 22, color: C.accent6, margin: 0, valign: "top", align: "left" }, text: "" } },
    { placeholder: { options: { name: "team", type: "body", x: 0.7, y: 5.55, w: 6.0, h: 0.45, fontSize: 18, bold: true, color: C.background1, margin: 0, valign: "top", align: "left" }, text: "" } },
  ],
});

pres.defineSlideMaster({
  title: "CONTENT",
  background: { color: C.background1 },
  objects: [
    { placeholder: { options: { name: "kicker", type: "body", x: MX, y: 0.42, w: CW, h: 0.3, fontSize: 12, bold: true, color: C.accent5, charSpacing: 1, margin: 0, valign: "top", align: "left" }, text: "" } },
    { placeholder: { options: { name: "title", type: "title", x: MX, y: 0.75, w: CW, h: 0.75, fontSize: 36, bold: true, color: C.text2, margin: 0, valign: "top", align: "left" }, text: "" } },
    { text: { text: "Parivaar Cover · Team Prometheus", options: { x: MX, y: 6.98, w: 6, h: 0.28, fontSize: 10, color: C.accent4, margin: 0, valign: "middle" } } },
  ],
  slideNumber: { x: W - MX - 0.6, y: 6.98, w: 0.6, h: 0.28, fontSize: 10, color: C.accent4, align: "right", valign: "middle", margin: 0 },
});

pres.defineSlideMaster({
  title: "CLOSING_DARK",
  background: { color: C.text2 },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: 0.7, y: 1.3, w: 11.9, h: 1.0, fontSize: 54, bold: true, color: C.background1, margin: 0, valign: "top", align: "left" }, text: "" } },
    { placeholder: { options: { name: "subtitle", type: "body", x: 0.7, y: 2.35, w: 11.9, h: 0.5, fontSize: 20, color: C.accent6, margin: 0, valign: "top", align: "left" }, text: "" } },
  ],
});

function contentSlide(section, kicker, title) {
  const s = pres.addSlide({ masterName: "CONTENT", sectionTitle: section });
  s.addText(kicker, { placeholder: "kicker" });
  s.addText(title, { placeholder: "title" });
  return s;
}

// ---------- slides ----------

async function build() {
  const I = {};
  const white = HEX.lt1;
  for (const n of ["LuMessageCircle", "LuFileSearch", "LuSlidersHorizontal", "LuShieldCheck", "LuUsers", "LuSmartphone", "LuBuilding2", "LuHandCoins", "LuRefreshCw", "LuWallet", "LuCode", "LuLock", "LuSparkles", "LuClock"]) {
    I[n] = await icon(n, white);
  }
  I.shieldSky = await icon("LuShieldCheck", HEX.accent1);
  I.heart = await icon("LuHeartPulse", HEX.accent5);
  I.check = await icon("LuCheck", HEX.accent3);
  I.cross = await icon("LuX", HEX.accent4);
  I.chevron = await icon("LuChevronRight", HEX.dk2);
  I.wallet = await icon("LuWallet", HEX.lt1);
  I.claim = await icon("LuFileX", HEX.lt1);
  I.trend = await icon("LuTrendingUp", HEX.lt1);

  // 1. Title
  pres.addSection({ title: "Title" });
  {
    const s = pres.addSlide({ masterName: "TITLE_DARK", sectionTitle: "Title" });
    s.addText("PAYTM HACKATHON 2026  ·  AI-POWERED FINANCIAL JOURNEYS", { placeholder: "kicker" });
    s.addText("Parivaar Cover", { placeholder: "title" });
    s.addText("Finds the best-value mix of health policies for your whole family, from kids to grandparents.", { placeholder: "subtitle" });
    s.addText("Team Prometheus", { placeholder: "team" });

    // family tree in a soft circle
    const cx = 10.35, d = 4.9;
    s.addShape(pres.shapes.OVAL, { x: cx - d / 2, y: 1.3, w: d, h: d, fill: { color: C.accent1, transparency: 85 }, line: { type: "none" }, objectName: "Family backdrop" });
    const av = 0.9;
    const tiers = [
      { y: 1.8, members: [["M", cx - 0.8], ["L", cx + 0.8]] },
      { y: 3.15, members: [["R", cx - 0.8], ["S", cx + 0.8]] },
      { y: 4.5, members: [["A", cx]] },
    ];
    for (const t of tiers) {
      for (const [i, mx] of t.members) {
        const m = fam(i);
        avatar(s, i, mx - av / 2, t.y, av, m.fill, 22);
        text(s, `${m.name}, ${m.age}`, mx - 0.8, t.y + av + 0.06, 1.6, 0.3, { fontSize: 12, color: C.background1, align: "center" });
      }
    }
    s.addShape(pres.shapes.OVAL, { x: 11.95, y: 4.85, w: 1.05, h: 1.05, fill: { color: C.background1 }, line: { type: "none" }, shadow: shadow(), objectName: "Shield badge" });
    s.addImage({ data: I.shieldSky, x: 12.18, y: 5.08, w: 0.6, h: 0.6 });
    s.addNotes("Parivaar Cover helps one person insure three generations of a family. It picks the mix of health policies that gives the most cover for the money.");
  }

  // 2. Problem
  pres.addSection({ title: "Problem" });
  {
    const s = contentSlide("Problem", "PROBLEM STATEMENT", "Insuring three generations is guesswork");

    // family card
    card(s, MX, 1.8, 3.7, 3.6, { name: "Family card" });
    text(s, "Rahul's family, Pune", MX + 0.3, 1.98, 3.2, 0.4, { fontSize: 16, bold: true, color: C.text2 });
    ["R", "S", "A", "M", "L"].forEach((i, k) => {
      const m = fam(i);
      const y = 2.52 + k * 0.55;
      avatar(s, i, MX + 0.3, y, 0.42, m.fill, 13);
      const runs = [{ text: `${m.name}, ${m.age}`, options: { bold: true, color: C.text2 } }];
      if (m.note) runs.push({ text: `   ${m.note}`, options: { color: C.accent5, italic: true } });
      text(s, runs, MX + 0.88, y, 2.6, 0.42, { fontSize: 15, valign: "middle" });
    });

    // decisions
    const qx = 4.75, qw = W - MX - qx;
    text(s, "What Rahul has to decide", qx, 1.8, qw, 0.4, { fontSize: 18, bold: true, color: C.text2 });
    const qs = [
      "One floater for all five, or separate plans for his parents?",
      "Is a super top-up worth adding, and at what deductible?",
      "Which of hundreds of plans, from dozens of insurers?",
      "What do co-pay, room-rent caps and waiting periods cost him?",
    ];
    qs.forEach((q, k) => {
      const y = 2.35 + k * 0.55;
      s.addText(String(k + 1), { shape: pres.shapes.OVAL, x: qx, y: y + 0.03, w: 0.38, h: 0.38, fill: { color: C.accent1 }, line: { type: "none" }, align: "center", valign: "middle", bold: true, fontSize: 13, color: C.text2, margin: 0, isTextBox: true });
      text(s, q, qx + 0.55, y, qw - 0.55, 0.44, { fontSize: 15, valign: "middle" });
    });
    card(s, qx, 4.62, qw, 0.78, { fill: { color: C.accent2, transparency: 78 }, name: "Gap callout" });
    text(s, "Agents push one big floater and comparison sites rank one policy at a time, so no one works out the mix for the whole family.", qx + 0.25, 4.62, qw - 0.5, 0.78, { fontSize: 15, valign: "middle", color: C.text2 });

    // stats strip
    const stats = [
      { img: I.wallet, n: "~40%", l: "of health spending in India is paid out of pocket", src: "National Health Accounts 2021-22" },
      { img: I.claim, n: "44%", l: "of claims rejected or only partly paid", src: "LocalCircles survey of policyholders, 2023-25" },
      { img: I.trend, n: "~12%", l: "medical inflation in 2024, about 3x general inflation", src: "Milliman" },
    ];
    const sw = (CW - 2 * 0.3) / 3;
    stats.forEach((st, k) => {
      const x = MX + k * (sw + 0.3);
      iconCircle(s, st.img, x, 5.68, 0.62, C.text2, `Stat icon ${k + 1}`);
      text(s, st.n, x + 0.8, 5.58, sw - 0.8, 0.45, { fontSize: 26, bold: true, color: C.text2, valign: "middle" });
      text(s, st.l, x + 0.8, 6.04, sw - 0.8, 0.45, { fontSize: 13 });
      text(s, st.src, x + 0.8, 6.5, sw - 0.8, 0.25, { fontSize: 10, color: C.accent4 });
    });
    s.addNotes("Rahul has to cover five people across three generations, one of them diabetic. Nobody helps him plan the combination. The numbers show what's at stake: families still pay about 40% of health costs themselves, and many claims get cut over fine print.");
  }

  // 3. Solution: journey
  pres.addSection({ title: "Solution" });
  {
    const s = contentSlide("Solution", "PROPOSED SOLUTION", "From family details to the right policy mix");
    const steps = [
      { img: I.LuMessageCircle, h: "Talk", b: "Chat or speak in English, Hindi or a regional language. Share each member's age, health, city and budget, plus any office cover." },
      { img: I.LuFileSearch, h: "Read the fine print", b: "AI has already turned every policy wording into comparable data: room rent, co-pay, waiting periods, sub-limits, network hospitals." },
      { img: I.LuSlidersHorizontal, h: "Optimise", b: "A solver tests thousands of floater, individual and top-up combinations and picks the most cover per rupee within budget." },
      { img: I.LuShieldCheck, h: "Explain and buy", b: "Each pick comes with a plain-language reason and its catches. Buy every policy in one Paytm checkout, with EMI if needed." },
    ];
    const gap = 0.3, cw = (CW - 3 * gap) / 4, y = 1.85, h = 3.55;
    steps.forEach((st, k) => {
      const x = MX + k * (cw + gap);
      card(s, x, y, cw, h, { name: `Step ${k + 1}` });
      iconCircle(s, st.img, x + 0.3, y + 0.3, 0.85, C.accent1, `Step ${k + 1} icon`);
      text(s, `0${k + 1}`, x + cw - 0.9, y + 0.35, 0.6, 0.4, { fontSize: 16, bold: true, color: C.accent5, align: "right" });
      text(s, st.h, x + 0.3, y + 1.4, cw - 0.6, 0.45, { fontSize: 18, bold: true, color: C.text2 });
      text(s, st.b, x + 0.3, y + 1.9, cw - 0.6, 1.8, { fontSize: 14 });
      if (k < 3) {
        const ax = x + cw + gap / 2 - 0.22;
        s.addShape(pres.shapes.OVAL, { x: ax, y: y + 0.52, w: 0.44, h: 0.44, fill: { color: C.background1 }, line: { color: C.accent6, width: 1 }, objectName: `Arrow ${k + 1}` });
        s.addImage({ data: I.chevron, x: ax + 0.1, y: y + 0.62, w: 0.24, h: 0.24 });
      }
    });
    card(s, MX, 5.7, CW, 0.66, { fill: { color: C.text2 }, name: "Time band" });
    iconCircle(s, I.LuClock, MX + 0.2, 5.78, 0.5, C.accent5, "Clock icon");
    text(s, "About 10 minutes from first question to recommendation, inside the Paytm app.", MX + 0.9, 5.7, CW - 1.2, 0.66, { fontSize: 16, bold: true, color: C.background1, valign: "middle" });
    s.addNotes("Four steps. The user talks, the AI has already read every policy, a solver builds the mix, and the app explains it before checkout. The solver does the maths, so the numbers are repeatable.");
  }

  // 4. Solution: Rahul's result
  {
    const s = contentSlide("Solution", "PROPOSED SOLUTION  ·  RAHUL'S FAMILY", "Rahul gets 4x the cover for ₹11,000 less");
    const y = 1.75, h = 4.0;

    // usual pick
    const lx = MX, lw = 4.2;
    card(s, lx, y, lw, h, { fill: { color: C.accent4, transparency: 90 }, name: "Usual pick card" });
    text(s, "THE USUAL PICK", lx + 0.3, y + 0.2, lw - 0.6, 0.3, { fontSize: 12, bold: true, color: C.accent4, charSpacing: 1 });
    text(s, "One ₹25L floater for all five", lx + 0.3, y + 0.55, lw - 0.6, 0.4, { fontSize: 18, bold: true, color: C.text2 });
    text(s, "₹1,18,000", lx + 0.3, y + 1.05, lw - 0.6, 0.7, { fontSize: 40, bold: true, color: C.text1 });
    text(s, "a year", lx + 0.3, y + 1.75, lw - 0.6, 0.3, { fontSize: 14, color: C.accent4 });
    text(s, [
      { text: "Five people share one ₹25L pool", options: { bullet: true, breakLine: true } },
      { text: "Priced on Mohan's age and diabetes", options: { bullet: true, breakLine: true } },
      { text: "Diabetes waiting period of 3 years", options: { bullet: true } },
    ], lx + 0.3, y + 2.2, lw - 0.6, 1.1, { fontSize: 14, paraSpaceAfter: 6 });
    s.addShape(pres.shapes.LINE, { x: lx + 0.3, y: y + 3.4, w: lw - 0.6, h: 0, line: { color: C.accent4, width: 0.75, transparency: 60 } });
    text(s, "Total cover", lx + 0.3, y + 3.5, 2, 0.4, { fontSize: 14, bold: true, color: C.text2, valign: "middle" });
    text(s, "₹25L", lx + lw - 2.3, y + 3.5, 2, 0.4, { fontSize: 18, bold: true, color: C.text1, align: "right", valign: "middle" });

    // the mix
    const rx = lx + lw + 0.3, rw = W - MX - rx;
    card(s, rx, y, rw, h, { fill: { color: C.background1 }, line: { color: C.accent1, width: 1.5 }, shadow: true, name: "Mix card" });
    text(s, "PARIVAAR COVER'S MIX", rx + 0.3, y + 0.2, 4, 0.3, { fontSize: 12, bold: true, color: C.accent5, charSpacing: 1 });
    text(s, "Five policies built for this family", rx + 0.3, y + 0.55, 4.6, 0.4, { fontSize: 18, bold: true, color: C.text2 });
    text(s, "₹1,07,000", rx + rw - 3.0, y + 0.15, 2.7, 0.6, { fontSize: 32, bold: true, color: C.text2, align: "right" });
    text(s, "a year", rx + rw - 3.0, y + 0.72, 2.7, 0.28, { fontSize: 14, color: C.accent4, align: "right" });
    const rows = [
      { who: ["R", "S", "A"], plan: "₹10L family floater", p: "₹21,000" },
      { who: ["R", "S", "A"], plan: "₹50L super top-up, ₹10L deductible", p: "₹4,500" },
      { who: ["M"], plan: "₹10L senior plan, 1-year diabetes wait", p: "₹41,000" },
      { who: ["L"], plan: "₹10L individual plan", p: "₹24,500" },
      { who: ["M", "L"], plan: "₹25L super top-up, ₹10L deductible", p: "₹16,000" },
    ];
    const ry0 = y + 1.15, rp = 0.45;
    rows.forEach((r, k) => {
      const ry = ry0 + k * rp;
      r.who.forEach((i, j) => avatar(s, i, rx + 0.3 + j * 0.28, ry + 0.04, 0.36, fam(i).fill, 11));
      text(s, r.plan, rx + 1.45, ry, rw - 3.0, rp, { fontSize: 14, valign: "middle" });
      text(s, r.p, rx + rw - 1.75, ry, 1.45, rp, { fontSize: 14, bold: true, color: C.text2, align: "right", valign: "middle" });
      s.addShape(pres.shapes.LINE, { x: rx + 0.3, y: ry + rp, w: rw - 0.6, h: 0, line: { color: C.accent6, width: 0.75 } });
    });
    text(s, "Total cover", rx + 0.3, y + 3.5, 2, 0.4, { fontSize: 14, bold: true, color: C.text2, valign: "middle" });
    text(s, "₹1.05 crore", rx + rw - 3.3, y + 3.5, 3.0, 0.4, { fontSize: 18, bold: true, color: C.accent3, align: "right", valign: "middle" });

    // claim check
    s.addImage({ data: I.heart, x: MX, y: 5.98, w: 0.36, h: 0.36 });
    text(s, [
      { text: "Claim check: ", options: { bold: true, color: C.text2 } },
      { text: "a ₹6L heart procedure for Mohan in year 2 is covered by the mix. With the usual pick it waits until year 4." },
    ], MX + 0.5, 5.92, CW - 0.5, 0.48, { fontSize: 14, valign: "middle" });
    text(s, "Illustrative premiums for a Pune family, rounded. Real quotes depend on the insurer and medical tests.", MX, 6.5, CW, 0.3, { fontSize: 10, color: C.accent4 });
    s.addNotes("The usual answer is one big floater for all five, priced on the oldest, sickest member. The mix gives the young family their own floater and a cheap top-up, gives each parent their own plan, and adds a top-up for the parents. It costs less and covers four times as much.");
  }

  // 5. Tech stack
  pres.addSection({ title: "Technology" });
  {
    const s = contentSlide("Technology", "TECHNOLOGY / TECH STACK", "How it's built");
    const layers = [
      { n: "Channels", d: "Where families use it", chips: ["Paytm mini-app (React Native)", "Web (React)", "Voice"] },
      { n: "AI layer", d: "Talks, reads policies, explains", chips: ["Claude Sonnet 5.5", "Bhashini / Sarvam AI (Indian languages)"] },
      { n: "Decision engine", d: "Builds the mix", chips: ["Python + FastAPI", "Google OR-Tools solver", "Claim simulator"] },
      { n: "Policy data", d: "Every plan as structured data", chips: ["PostgreSQL + pgvector", "PDF parsing pipeline", "Human review"] },
      { n: "Integrations", d: "Quote, pay, issue", chips: ["Paytm Insurance Broking", "Paytm KYC & payments", "Lending partners (EMI)"] },
    ];
    const lw = 9.3, lh = 0.7, lg = 0.13, y0 = 1.8;
    layers.forEach((L, k) => {
      const y = y0 + k * (lh + lg);
      card(s, MX, y, lw, lh, { radius: 0.1, name: `Layer ${L.n}` });
      text(s, L.n, MX + 0.25, y + 0.1, 2.3, 0.3, { fontSize: 14, bold: true, color: C.text2 });
      text(s, L.d, MX + 0.25, y + 0.38, 2.3, 0.25, { fontSize: 11, color: C.accent4 });
      let cx = MX + 2.65;
      L.chips.forEach((c) => {
        const cwid = c.length * 0.08 + 0.34;
        s.addText(c, { shape: pres.shapes.ROUNDED_RECTANGLE, rectRadius: 0.08, x: cx, y: y + 0.15, w: cwid, h: 0.4, fill: { color: C.background1 }, line: { color: C.accent6, width: 1 }, fontSize: 12, color: C.text1, align: "center", valign: "middle", margin: 0, isTextBox: true });
        cx += cwid + 0.12;
      });
    });
    // trust pillar
    const px = MX + lw + 0.2, pw = W - MX - px, ph = 5 * lh + 4 * lg;
    card(s, px, y0, pw, ph, { fill: { color: C.text2 }, name: "Trust pillar" });
    iconCircle(s, I.LuLock, px + 0.3, y0 + 0.3, 0.6, C.accent5, "Lock icon");
    text(s, "Trust and compliance", px + 0.3, y0 + 1.05, pw - 0.6, 0.65, { fontSize: 16, bold: true, color: C.background1 });
    text(s, [
      { text: "DPDP Act consent", options: { bullet: true, breakLine: true } },
      { text: "Encrypted health data", options: { bullet: true, breakLine: true } },
      { text: "Audit log for every recommendation", options: { bullet: true } },
    ], px + 0.3, y0 + 1.8, pw - 0.5, 2.0, { fontSize: 13, color: C.accent6, paraSpaceAfter: 8 });
    // guardrail
    card(s, MX, 6.0, CW, 0.62, { fill: { color: C.accent2, transparency: 78 }, name: "Guardrail callout" });
    iconCircle(s, I.LuSparkles, MX + 0.18, 6.07, 0.48, C.text2, "Sparkles icon");
    text(s, "Prices and picks come from the solver. The LLM explains them and cites the policy clause.", MX + 0.85, 6.0, CW - 1.1, 0.62, { fontSize: 15, bold: true, color: C.text2, valign: "middle" });
    s.addNotes("The LLM handles language: the conversation, reading policy PDFs, and explaining results. A deterministic solver picks the plans, so every number can be traced. Policy data is extracted by AI and checked by a person.");
  }

  // 6. USP
  pres.addSection({ title: "USP" });
  {
    const s = contentSlide("USP", "USP", "How it compares");
    const cols = [5.5, 2.0, 2.0, 2.6];
    const xs = cols.reduce((a, w, k) => (a.push(k ? a[k - 1] + cols[k - 1] : MX), a), []);
    const hy = 1.8, hh = 0.6, rh = 0.62;
    const rows = [
      ["Recommends a mix of policies for the whole family", "Sometimes", "no", "yes"],
      ["Compares plans across insurers", "Partly", "yes", "yes"],
      ["Explains the fine print before you pay", "Partly", "Partly", "yes"],
      ["Shows your out-of-pocket cost for real treatments", "no", "no", "yes"],
      ["Talks in your language, by voice", "yes", "no", "yes"],
    ];
    const tableBottom = hy + hh + rows.length * rh;
    card(s, xs[3], hy - 0.1, cols[3], tableBottom - hy + 0.2, { line: { color: C.accent1, width: 1.5 }, name: "Our column" });
    ["Insurance agent", "Comparison site", "Parivaar Cover"].forEach((h, k) => {
      text(s, h, xs[k + 1], hy, cols[k + 1], hh, { fontSize: 15, bold: true, align: "center", valign: "middle", color: k === 2 ? C.accent5 : C.text2 });
    });
    rows.forEach((r, k) => {
      const y = hy + hh + k * rh;
      s.addShape(pres.shapes.LINE, { x: MX, y, w: xs[3] - MX, h: 0, line: { color: C.accent6, width: 0.75 } });
      text(s, r[0], MX, y, cols[0] - 0.2, rh, { fontSize: 15, valign: "middle" });
      for (let c = 1; c <= 3; c++) {
        const cx = xs[c] + cols[c] / 2;
        if (r[c] === "yes" || r[c] === "no") {
          s.addImage({ data: r[c] === "yes" ? I.check : I.cross, x: cx - 0.18, y: y + rh / 2 - 0.18, w: 0.36, h: 0.36 });
        } else {
          text(s, r[c], xs[c], y, cols[c], rh, { fontSize: 13, italic: true, color: C.accent4, align: "center", valign: "middle" });
        }
      }
    });
    iconCircle(s, I.LuSmartphone, MX, 5.85, 0.62, C.text2, "Phone icon");
    text(s, "Runs inside Paytm, so KYC, payments and renewal reminders are already in place.", MX + 0.85, 5.85, CW - 0.85, 0.62, { fontSize: 16, bold: true, color: C.text2, valign: "middle" });
    s.addNotes("Agents and comparison sites each do part of the job. None of them plans a multi-policy mix for a whole family, and none shows what you'd actually pay out of pocket for a real treatment.");
  }

  // 7. Impact
  pres.addSection({ title: "Impact" });
  {
    const s = contentSlide("Impact", "IMPACT & BENEFITS", "Who benefits");
    const gap = 0.3, bw = (CW - 2 * gap) / 3;
    const stats = [
      ["~10 min", "from first question to recommendation (target)"],
      ["4x", "the cover for ₹11,000 less in Rahul's case"],
      ["3 to 5", "policies per family, instead of one"],
    ];
    stats.forEach(([n, l], k) => {
      const x = MX + k * (bw + gap);
      text(s, n, x, 1.75, bw, 0.7, { fontSize: 40, bold: true, color: C.text2 });
      text(s, l, x, 2.45, bw, 0.35, { fontSize: 13, color: C.accent4 });
    });
    const groups = [
      { img: I.LuUsers, h: "Families", b: ["Decide in one sitting", "Parents get proper cover (no age cap on new policies since 2024)", "See waiting periods and caps before paying"] },
      { img: I.LuSmartphone, h: "Paytm", b: ["Bigger ticket per household", "Renewals and yearly check-ups bring families back", "Uses Paytm's KYC, payments and lending"] },
      { img: I.LuBuilding2, h: "Insurers", b: ["Customers matched to the right product", "Fewer disputes at claim time", "Lower cost to acquire customers"] },
    ];
    groups.forEach((g, k) => {
      const x = MX + k * (bw + gap), y = 3.1, h = 3.15;
      card(s, x, y, bw, h, { name: `${g.h} card` });
      iconCircle(s, g.img, x + 0.3, y + 0.3, 0.7, C.accent1, `${g.h} icon`);
      text(s, g.h, x + 1.2, y + 0.3, bw - 1.5, 0.7, { fontSize: 20, bold: true, color: C.text2, valign: "middle" });
      text(s, g.b.map((t, j) => ({ text: t, options: { bullet: true, breakLine: j < g.b.length - 1 } })), x + 0.3, y + 1.25, bw - 0.6, h - 1.45, { fontSize: 14, paraSpaceAfter: 8 });
    });
    s.addNotes("Families get a better plan in one sitting. Paytm sells several policies per household and renews them every year. Insurers get customers who bought the right product, which means fewer disputes later.");
  }

  // 8. Business model
  pres.addSection({ title: "Business model" });
  {
    const s = contentSlide("Business model", "BUSINESS MODEL", "Free for families, paid by insurer brokerage");
    const streams = [
      { img: I.LuHandCoins, h: "Brokerage", b: "Insurers pay brokerage on each policy via Paytm Insurance Broking (IRDAI licensed to 2029). A family buys 3 to 5." },
      { img: I.LuRefreshCw, h: "Renewals", b: "Health cover renews every year. A yearly check-up re-runs the optimizer and keeps the family on Paytm." },
      { img: I.LuWallet, h: "Premium EMI", b: "Lending partners split large premiums into monthly payments. Paytm earns a share." },
      { img: I.LuCode, h: "B2B API", b: "Employers and other distributors license the optimizer." },
    ];
    const gw = 7.6, gap = 0.25, cw = (gw - gap) / 2, ch = 2.05, y0 = 1.8;
    streams.forEach((st, k) => {
      const x = MX + (k % 2) * (cw + gap), y = y0 + Math.floor(k / 2) * (ch + gap);
      card(s, x, y, cw, ch, { name: `${st.h} card` });
      iconCircle(s, st.img, x + 0.25, y + 0.25, 0.55, C.accent1, `${st.h} icon`);
      text(s, st.h, x + 0.95, y + 0.25, cw - 1.2, 0.55, { fontSize: 17, bold: true, color: C.text2, valign: "middle" });
      text(s, st.b, x + 0.25, y + 0.95, cw - 0.5, ch - 1.1, { fontSize: 14 });
    });
    // illustration panel
    const px = MX + gw + 0.3, pw = W - MX - px, ph = 2 * ch + gap;
    card(s, px, y0, pw, ph, { fill: { color: C.text2 }, name: "Year 1 panel" });
    text(s, "YEAR 1 ILLUSTRATION", px + 0.35, y0 + 0.25, pw - 0.7, 0.3, { fontSize: 12, bold: true, color: C.accent1, charSpacing: 1 });
    const lines = [
      ["50,000", "families"],
      ["× ₹70,000", "average yearly premium"],
      ["= ₹350 Cr", "premium through Paytm"],
    ];
    lines.forEach(([n, l], k) => {
      const y = y0 + 0.65 + k * 0.82;
      text(s, n, px + 0.35, y, pw - 0.7, 0.45, { fontSize: 26, bold: true, color: C.background1 });
      text(s, l, px + 0.35, y + 0.45, pw - 0.7, 0.28, { fontSize: 12, color: C.accent6 });
    });
    s.addShape(pres.shapes.LINE, { x: px + 0.35, y: y0 + 3.15, w: pw - 0.7, h: 0, line: { color: C.accent6, width: 0.75, transparency: 50 } });
    text(s, "₹42 Cr", px + 0.35, y0 + 3.25, pw - 0.7, 0.55, { fontSize: 32, bold: true, color: C.accent2 });
    text(s, "revenue at an assumed 12% brokerage, before renewals", px + 0.35, y0 + 3.8, pw - 0.7, 0.5, { fontSize: 12, color: C.accent6 });
    text(s, "Main costs: AI usage per session, keeping policy data current, insurer integrations.", MX, 6.42, CW, 0.3, { fontSize: 12, color: C.accent4 });
    s.addNotes("Families pay the same premium they would anywhere else. Revenue comes from brokerage on several policies per family, renewals every year, a share of premium EMI, and licensing the optimizer to employers. The year 1 figures are an illustration with stated assumptions.");
  }

  // 9. Close
  pres.addSection({ title: "Close" });
  {
    const s = pres.addSlide({ masterName: "CLOSING_DARK", sectionTitle: "Close" });
    s.addText("Thank you", { placeholder: "title" });
    s.addText("Parivaar Cover  ·  Team Prometheus", { placeholder: "subtitle" });
    text(s, "WHAT'S NEXT", 0.7, 3.65, 6, 0.3, { fontSize: 13, bold: true, color: C.accent1, charSpacing: 1 });
    const steps = [
      ["Round 2", "Working prototype on real policy data"],
      ["Pilot", "Live with a small group of Paytm users"],
      ["Scale", "Yearly check-ups and the employer API"],
    ];
    const colw = 3.9, d = 0.6, cy = 4.2;
    s.addShape(pres.shapes.LINE, { x: 0.7 + d / 2, y: cy + d / 2, w: 2 * colw, h: 0, line: { color: C.accent6, width: 1.25, transparency: 40 } });
    steps.forEach(([h, b], k) => {
      const x = 0.7 + k * colw;
      s.addText(String(k + 1), { shape: pres.shapes.OVAL, x, y: cy, w: d, h: d, fill: { color: C.accent1 }, line: { type: "none" }, align: "center", valign: "middle", bold: true, fontSize: 18, color: C.text2, margin: 0, isTextBox: true });
      text(s, h, x, cy + 0.8, colw - 0.4, 0.4, { fontSize: 18, bold: true, color: C.background1 });
      text(s, b, x, cy + 1.22, colw - 0.4, 0.7, { fontSize: 14, color: C.accent6 });
    });
    s.addNotes("Next round: a working prototype on real policy data. After that, a small pilot with Paytm users.");
  }

  await pres.writeFile({ fileName: OUT });
  await applyTheme(OUT, THEME);
  console.log("wrote", OUT);
}

build().catch((e) => { console.error(e); process.exit(1); });
