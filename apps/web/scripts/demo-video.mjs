// Records the 3-minute demo video: one walk through the four roles, with captions.
// Usage: node scripts/demo-video.mjs [baseUrl] [outFile] [caseSubject]   (app and API must be running)
// caseSubject: the queue row to open — pick an open AI-arm case the model got right.
import { mkdirSync, renameSync } from "node:fs";
import { dirname, join } from "node:path";
import { chromium } from "@playwright/test";

const base = process.argv[2] ?? "http://localhost:5173";
const outFile = process.argv[3] ?? "../../docs/demo/demo.webm";
const caseSubject = process.argv[4] ?? "Accident - contrat CT84905122";
const tmp = join(dirname(outFile), ".rec");
mkdirSync(tmp, { recursive: true });

const size = { width: 1440, height: 900 };
const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: size, recordVideo: { dir: tmp, size } });

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
  };
  if (document.body) mount(); else addEventListener("DOMContentLoaded", mount);
});

const page = await ctx.newPage();
const wait = (ms) => page.waitForTimeout(ms);

async function caption(text, ms = 3200) {
  await page.evaluate((t) => {
    const cap = document.getElementById("__demo_caption");
    if (!cap) return;
    cap.textContent = t;
    cap.style.opacity = t ? "1" : "0";
  }, text);
  if (ms) await wait(ms);
}

async function click(locator, pause = 900) {
  const box = await locator.boundingBox();
  if (box) {
    await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2, { steps: 12 });
    await wait(350);
  }
  await locator.click();
  await wait(pause);
}

async function loginAs(role, name) {
  await page.goto(`${base}/connexion`);
  await page.waitForLoadState("networkidle");
  await click(page.getByRole("radio", { name: new RegExp(role) }), 500);
  const input = page.getByRole("textbox");
  await input.fill(name);
  await click(page.getByRole("button", { name: /Entrer/ }), 1200);
  await page.waitForLoadState("networkidle");
}

// 1 — the idea
await page.goto(`${base}/connexion`);
await page.waitForLoadState("networkidle");
await caption("Tri & Mesure : l'IA propose, un humain décide, l'outil mesure.", 4200);
await caption("Quatre métiers, quatre écrans. On commence par Sophie, gestionnaire sinistres.", 3800);
await loginAs("Gestionnaire", "Sophie");

// 2 — the queue
await caption("Sa corbeille : les e-mails sinistres, les plus urgents d'abord.", 3800);
await page.mouse.move(700, 520, { steps: 15 });
await caption("Priorité et délai sont calculés par des règles lisibles, pas par l'IA.", 3800);
await caption("« Traiter le dossier suivant » ouvre le plus urgent ; ici, on ouvre un accident.", 0);
await click(page.getByText(caseSubject).first(), 1500);
await page.getByText("Proposition de").first().waitFor({ timeout: 20_000 });

// 3 — one case
await caption("Un dossier : l'e-mail, la proposition de l'IA, et le contexte.", 4000);
await caption("Les données personnelles sont masquées avant d'être envoyées à l'IA.", 3600);
const source = page.getByRole("button", { name: /^Voir .* dans l'e-mail$/ }).first();
if (await source.count()) {
  await caption("Chaque valeur renvoie au passage de l'e-mail qui la justifie.", 0);
  await click(source, 2600);
}
const contrat = page.getByRole("tab", { name: /Contrat/ });
await caption("À côté : le contrat. Ici, la grêle n'est pas couverte : à dire au client.", 0);
await click(contrat, 3800);
await caption("Et une réponse type, déjà remplie, à copier.", 0);
await click(page.getByRole("tab", { name: /Réponse/ }), 2400);
await click(page.getByRole("tab", { name: /À faire/ }), 1200);
const confirm = page.getByRole("button", { name: /^Confirmer$/ });
if (await confirm.count()) {
  await caption("Quand l'IA n'est pas sûre, Sophie doit confirmer : pas de validation par réflexe.", 0);
  await click(confirm, 2200);
}
const validate = page.getByRole("button", { name: /^Valider$/ });
if (await validate.isEnabled()) {
  await caption("Elle valide. Le dossier suivant s'ouvre tout seul ; tout est tracé.", 0);
  await click(validate, 3000);
}

// 4 — the manager
await loginAs("Responsable", "Inès");
await page.getByText("Mode tempête").first().waitFor({ timeout: 15_000 });
await caption("Inès, responsable d'équipe : stock, retards, et la valeur réelle de l'IA.", 4200);
await page.mouse.move(1000, 700, { steps: 15 });
await caption("La moitié des dossiers est traitée sans IA : c'est la référence qui prouve le gain.", 4600);
await caption("Mode tempête : simuler une vague d'e-mails après un orage, et voir si l'équipe tient.", 4200);

// 5 — the auditor
await loginAs("Auditeur", "Paul");
await caption("Paul, auditeur : chaque action, humaine ou IA, est inscrite au journal.", 3800);
await click(page.getByRole("button", { name: /Vérifier l'intégrité/ }), 2200);
await caption("Les entrées sont chaînées : une modification après coup se voit immédiatement.", 4200);

// 6 — the AI team
await loginAs("Équipe IA", "Lucas");
await caption("Lucas, équipe IA : toutes les IA sont comparées sur les mêmes dossiers.", 4000);
await caption("N'importe quel fournisseur peut se brancher ; le meilleur devient le champion.", 4200);

await caption("Tri & Mesure — prototype étudiant, données entièrement fictives.", 3800);
await caption("", 500);

const video = page.video();
await ctx.close();
await browser.close();
renameSync(await video.path(), outFile);
console.log("saved", outFile);
