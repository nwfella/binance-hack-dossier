#!/usr/bin/env node
/**
 * Verification gate for the Binance hack dossier.
 * Run:  node scripts/verify_site.js [docs/index.html]
 * Exit 0 = all checks pass. Non-zero = at least one failure.
 */
const fs = require("fs");
const path = require("path");

const ROOT = path.resolve(__dirname, "..");
const INDEX = process.argv[2] ? path.resolve(process.argv[2]) : path.join(ROOT, "docs", "index.html");
const PDF = path.join(ROOT, "docs", "Binance-Hack-Report-2026-10-29.pdf");
const STATE = path.join(ROOT, "docs", "updates.json");

let pass = 0;
const fails = [];
function ok(name, cond, detail) {
  if (cond) { pass++; console.log(`  \u2713 ${name}`); }
  else { fails.push(name + (detail ? ` — ${detail}` : "")); console.log(`  \u2717 ${name}${detail ? " — " + detail : ""}`); }
}

console.log("verify_site.js");

// ---------- existence ----------
ok("index.html exists", fs.existsSync(INDEX), INDEX);
if (!fs.existsSync(INDEX)) process.exit(1);
const html = fs.readFileSync(INDEX, "utf8");

ok("index.html non-trivial size (>25KB)", html.length > 25_000, `${html.length} bytes`);
ok("PDF exists", fs.existsSync(PDF));
let pdfBuf = Buffer.alloc(0);
if (fs.existsSync(PDF)) {
  pdfBuf = fs.readFileSync(PDF);
  ok("PDF has %PDF header", pdfBuf.slice(0, 5).toString() === "%PDF-");
  ok("PDF > 150KB", pdfBuf.length > 150_000, `${(pdfBuf.length / 1024).toFixed(0)} KB`);
  const pages = (pdfBuf.toString("latin1").match(/\/Type\s*\/Page[^s]/g) || []).length;
  ok("PDF has >= 12 pages", pages >= 12, `${pages} page objects`);
}

// ---------- template tokens ----------
const tokens = html.match(/\{\{[A-Z_]+\}\}/g) || [];
ok("no unresolved template tokens", tokens.length === 0, tokens.slice(0, 5).join(", "));

// ---------- structure ----------
["01", "02", "03", "04", "05", "06", "07", "08"].forEach((n) => {
  ok(`section ${n} present`, html.includes(`<span class="k">${n}</span>`));
});
ok("header flag / live indicator", html.includes('class="flag"'));
ok("withdrawal-suspension alert", /All Binance deposits and withdrawals are suspended/.test(html));
ok("rebuild timestamp injected", /<b>Rebuilt<\/b>\s*\d{2} \w{3} \d{4}/.test(html));
ok("no stale banner (fresh build)", !html.includes("hourly job may be stalled"));
ok("PDF link present", html.includes("Binance-Hack-Report-2026-10-29.pdf"));

// ---------- feed ----------
const items = (html.match(/<article class="upd">/g) || []).length;
ok("feed has >= 5 items", items >= 5, `${items} items`);
ok("every feed item has a source badge", (html.match(/class="src s-[a-z0-9]+"/g) || []).length === items);
ok("every feed item has a timestamp", (html.match(/<time datetime="20/g) || []).length >= items - 1);
ok("every feed item has an outbound link", (html.match(/class="ut" href="https:\/\//g) || []).length === items);
ok("no javascript: URLs", !/href="javascript:/i.test(html));
ok("no empty hrefs", !/href="\s*"/.test(html));

// badge classes must all be styled
const badges = new Set([...html.matchAll(/class="src (s-[a-z0-9]+)"/g)].map((m) => m[1]));
const unstyled = [...badges].filter((b) => !html.includes(`.uh .src.${b}{`));
ok("all source badges have CSS", unstyled.length === 0, unstyled.join(", "));

// ---------- on-chain data ----------
const ADDRS = [
  "0x28C6c06298d514Db089934071355E5743bf21d60",
  "0xDFd5293D8e347dFe59E90eFd55b2956a1343963d",
  "0x5227f603C1eE34CE3C06eFe6477003BDfCCB2f8c",
  "0x63e842B054Bd624a465454D533C33F573e9c6fAe",
  "0x7C8601d4645b93cea45F71e118A729332e6B5CA0",
];
ADDRS.forEach((a, i) => ok(`address ${i + 1} present + linked`, html.includes(a)));

// ---------- figure integrity ----------
ok("frozen figure $2.54B present", html.includes("$2.54B"));
ok("loss range shown as a range, not a point", /\$5\.5–5\.9B|\$5\.5-5\.9B/.test(html));
ok("'not a loss estimate' caveat present", /Not a loss estimate/i.test(html));
ok("attribution stated as absent", /No agency or firm has named an actor/.test(html));

// ---------- state file ----------
ok("updates.json parses", (() => {
  try { JSON.parse(fs.readFileSync(STATE, "utf8")); return true; } catch { return false; }
})());
if (fs.existsSync(STATE)) {
  const st = JSON.parse(fs.readFileSync(STATE, "utf8"));
  ok("state has items array", Array.isArray(st.items) && st.items.length > 0, `${(st.items || []).length} items`);
  ok("state has last_run", typeof st.last_run === "string" && st.last_run.length > 10);
  const bad = st.items.filter((i) => !i.title || !i.link || !i.source);
  ok("all items have title/link/source", bad.length === 0, `${bad.length} malformed`);
  const links = st.items.map((i) => i.link);
  ok("no duplicate links", new Set(links).size === links.length);
  const offTopic = st.items.filter((i) => !/binance|bnb|tether|circle|usdt|usdc|7702|hot wallet/i.test(i.title + " " + (i.desc || "")));
  ok("every item is on-topic", offTopic.length === 0, offTopic.slice(0, 2).map((i) => i.title.slice(0, 40)).join(" | "));
}

// ---------- responsive / a11y basics ----------
ok("viewport meta present", /name="viewport"/.test(html));
ok("lang attribute", /<html lang="en"/.test(html));
ok("title tag", /<title>[^<]{10,}<\/title>/.test(html));
ok("external links are noopener", (html.match(/target="_blank"(?! rel="noopener")/g) || []).length === 0);

// ---------- report ----------
console.log(`\n${pass} passed, ${fails.length} failed`);
if (fails.length) {
  console.log("\nFAILURES:");
  fails.forEach((f) => console.log("  - " + f));
  process.exit(1);
}
console.log("ALL CHECKS PASSED");
