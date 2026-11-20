// Step 2 of the demo video: one walk through the four roles, captioned, timed by the voice.
// Usage: node scripts/demo-video.mjs [baseUrl] [caseSubject]   (app and API must be running)
//   caseSubject: the queue row to open; pick an open AI-arm case the model got right.
// Reads tools/demo/narration.json (+ out/durations.json from voice.py, if present);
// writes tools/demo/out/raw.webm and out/marks.json (when each caption appeared) for mux.py.
import { existsSync, mkdirSync, readFileSync, renameSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "@playwright/test";

const base = process.argv[2] ?? "http://localhost:5173";
const caseSubject = process.argv[3] ?? "Rapport d'expertise";
const demo = join(dirname(fileURLToPath(import.meta.url)), "../../../tools/demo");
const out = join(demo, "out");
mkdirSync(join(out, ".rec"), { recursive: true });

const spec = JSON.parse(readFileSync(join(demo, "narration.json"), "utf8"));
const durations = existsSync(join(out, "durations.json"))
  ? JSON.parse(readFileSync(join(out, "durations.json"), "utf8"))
  : {};
const segments = Object.fromEntries(spec.segments.map((s) => [s.id, s]));

const size = { width: 1440, height: 900 };
const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: size, recordVideo: { dir: join(out, ".rec"), size } });

// A visible pointer and a caption bar, re-created on every page load.
await ctx.addInitScript(() => {
  const mount = () => {
    if (document.getElementById("__demo_cursor")) return;
    const c = document.createElement("div");
    c.id = "__demo_cursor";
    c.style.cssText = "position:fixed;z-index:99999;width:22px;height:22px;border-radius:50%;background:rgba(255,71,81,.35);border:2px solid #ff4751;pointer-events:none;transform:translate(-50%,-50%);transition:left .25s,top .25s;left:-50px;top:-50px";
    document.body.appendChild(c);
    addEventListener("mousemove", (e) => { c.style.left = e.clientX + "px"; c.style.top = e.clientY + "px"; }, true);
    const cap = document.createElement("div");
    cap.id = "__demo_caption";
    cap.style.cssText = "position:fixed;z-index:99998;left:50%;bottom:28px;transform:translateX(-50%);max-width:900px;padding:14px 26px;border-radius:999px;background:rgba(13,14,51,.92);color:#fff;font:600 20px 'Source Sans 3',system-ui,sans-serif;text-align:center;box-shadow:0 10px 30px rgba(0,0,0,.25);opacity:0;transition:opacity .3s;pointer-events:none";
    document.body.appendChild(cap);
    const saved = sessionStorage.getItem("__demo_caption");
    if (saved) { cap.textContent = saved; cap.style.opacity = "1"; }
  };
  if (document.body) mount(); else addEventListener("DOMContentLoaded", mount);
});

const page = await ctx.newPage();
const t0 = Date.now(); // the recording starts with the page
const wait = (ms) => page.waitForTimeout(ms);
const marks = [];
let speechEnd = 0;

/** Wait until the current sentence has been said (plus a short breath). */
async function finish(min = 0) {
  const left = Math.max(speechEnd - Date.now(), min);
  if (left > 0) await wait(left);
}

/** Show a caption and start its sentence; the walk can keep moving while it is said. */
async function say(id) {
  await finish();
  const seg = segments[id];
  const text = id ? seg.caption : "";
  await page.evaluate((t) => {
    sessionStorage.setItem("__demo_caption", t);
    const cap = document.getElementById("__demo_caption");
    if (!cap) return;
    cap.textContent = t;
    cap.style.opacity = t ? "1" : "0";
  }, text);
  if (!id) return;
  marks.push({ id, t: Date.now() - t0 });
  const ms = durations[id] ?? Math.max(2500, text.length * 55);
  speechEnd = Date.now() + ms + 450;
}

async function click(locator, pause = 700) {
  const box = await locator.boundingBox();
  if (box) {
    await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2, { steps: 12 });
    await wait(300);
  }
  await locator.click();
  await wait(pause);
}

async function loginAs(role, name) {
  await say(""); // the previous sentence ends, its caption leaves with it
  await page.goto(`${base}/connexion`);
  await page.waitForLoadState("networkidle");
  await click(page.getByRole("radio", { name: new RegExp(role) }), 400);
  await page.getByRole("textbox").fill(name);
  await click(page.getByRole("button", { name: /Entrer/ }), 900);
  await page.waitForLoadState("networkidle");
}

// 1 — the idea
await page.goto(`${base}/connexion`);
await page.waitForLoadState("networkidle");
await wait(600);
await say("intro");
await say("roles");
await finish();
await loginAs("Gestionnaire", "Sophie");

// 2 — the queue
await say("queue");
await page.mouse.move(700, 520, { steps: 15 });
await say("rules");
await page.mouse.move(760, 400, { steps: 15 });
await say("open");
await finish(-1200);
await click(page.getByText(caseSubject).first(), 1200);
await page.getByText("Proposition de").first().waitFor({ timeout: 20_000 });

// 3 — one case
await say("case");
await say("privacy");
const source = page.getByRole("button", { name: /^Voir .* dans l'e-mail$/ }).first();
if (await source.count()) {
  await say("source");
  await click(source, 600);
}
await say("contract");
await click(page.getByRole("tab", { name: /Contrat/ }), 600);
await say("reply");
await click(page.getByRole("tab", { name: /Réponse/ }), 600);
await finish();
await click(page.getByRole("tab", { name: /À faire/ }), 500);
const confirm = page.getByRole("button", { name: /^Confirmer$/ });
if (await confirm.count()) {
  await say("confirm");
  await finish(-1500);
  await click(confirm, 500);
}
const validate = page.getByRole("button", { name: /^Valider$/ });
if (await validate.isEnabled()) {
  await say("validate");
  await click(validate, 800);
}
await finish();

// 4 — the manager
await loginAs("Responsable", "Inès");
await page.getByText("Mode tempête").first().waitFor({ timeout: 15_000 });
await say("manager");
await page.mouse.move(1000, 700, { steps: 15 });
await say("control");
await page.mouse.move(700, 420, { steps: 15 });
await say("storm");
await finish();

// 5 — the auditor
await loginAs("Auditeur", "Paul");
await say("auditor");
await click(page.getByRole("button", { name: /Vérifier l'intégrité/ }), 600);
await say("chain");
await finish();

// 6 — the AI team
await loginAs("Équipe IA", "Lucas");
await say("aiteam");
await say("vendors");
await say("outro");
await finish();
await say("");
await wait(500);

const video = page.video();
await ctx.close();
await browser.close();
renameSync(await video.path(), join(out, "raw.webm"));
writeFileSync(join(out, "marks.json"), JSON.stringify(marks, null, 1));
console.log(`saved ${join(out, "raw.webm")} · ${marks.length} captions · ${Math.round((Date.now() - t0) / 1000)} s`);
