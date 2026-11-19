// Capture every screen per role (for design review and the README).
// Usage: node scripts/screens.mjs [baseUrl] [outDir]   (app and API must be running)
import { mkdirSync } from "node:fs";
import { chromium } from "@playwright/test";

const base = process.argv[2] ?? "http://localhost:5173";
const out = process.argv[3] ?? "screens";
mkdirSync(out, { recursive: true });

const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 });
const page = await ctx.newPage();

async function loginAs(roleLabel) {
  await page.goto(`${base}/connexion`);
  await page.getByRole("radio", { name: new RegExp(roleLabel) }).click();
  await page.getByRole("button", { name: /Entrer/ }).click();
  await page.waitForLoadState("networkidle");
}

async function shot(name, path, waitFor) {
  if (path) await page.goto(`${base}${path}`);
  await page.waitForLoadState("networkidle");
  if (waitFor) await page.getByText(waitFor).first().waitFor({ timeout: 10_000 }).catch(() => {});
  await page.waitForTimeout(400);
  await page.screenshot({ path: `${out}/${name}.png` });
  console.log("saved", name);
}

await page.goto(`${base}/connexion`);
await shot("00-connexion", null, "Qui êtes-vous");

await loginAs("Gestionnaire");
await shot("10-corbeille", "/", "Dossiers");
await page.getByRole("button", { name: /Traiter le dossier suivant/ }).click().catch(() => {});
await page.waitForURL(/dossier/, { timeout: 10_000 }).catch(() => {});
await shot("11-dossier", null, "Proposition de");
await page.getByRole("button", { name: /Aide sur cet écran/ }).click();
await shot("12-dossier-aide", null, "Comment ça marche");
await page.keyboard.press("Escape");

await loginAs("Responsable");
await shot("20-pilotage", "/pilotage", "Stock");

await loginAs("Auditeur");
await shot("30-journal", "/journal", "Registre");

await loginAs("Équipe IA");
await shot("40-ia", "/ia", "Tour de contrôle");

await browser.close();
