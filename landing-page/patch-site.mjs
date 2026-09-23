// Reapply the audit fixes to the existing deployment, preserving its components.
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';

const root = path.dirname(fileURLToPath(import.meta.url));
const require = createRequire(path.join(root, '../frontend/package.json'));
const ts = require('typescript');
const cheerio = createRequire(path.join(root, 'package.json'))('cheerio');
const host = path.join(root, 'site-mirror/www.sammylabs.com');
const chunks = path.join(host, '_next/static/chunks');
const find = (directory, prefix) => path.join(directory, fs.readdirSync(directory).find((name) => name.startsWith(prefix)));
function capture(file) {
  const source = fs.readFileSync(file, 'utf8');
  const context = { self: { webpackChunk_N_E: [] } };
  vm.runInNewContext(source, context);
  return { source, modules: context.self.webpackChunk_N_E[0][1] };
}
const md = fs.readFileSync(path.join(root, 'content.md'), 'utf8').replaceAll('â€™', '’').replaceAll('â€”', '—').replaceAll('â€¦', '…').replaceAll('Â·', '·');
const section = (name) => md.split(`## ${name}\n`)[1]?.split('\n## ')[0];
const field = (text, label) => {
  const match = text.match(new RegExp(`${label}:\\s*(?:\\n\\n)?\\*\\*([^]*?)\\*\\*`));
  if (!match) throw new Error(`Missing copy: ${label}`);
  return match[1].trim();
};
const copyFile = find(chunks, '347-');
const shared = capture(copyFile);
const copy = {};
const runtime = () => { throw new Error('Unexpected dependency'); };
runtime.d = (target, getters) => { for (const [name, get] of Object.entries(getters)) Object.defineProperty(target, name, { get, enumerable: true }); };
shared.modules[9941]({}, copy, runtime);
const data = JSON.parse(JSON.stringify(copy));
const form = section('Access form');
data.L3.form = {
  button: field(section('Hero'), 'Primary button'), emailLabel: 'Work email', placeholder: 'you@organisation.com',
  submit: field(form, 'Submit button'), sending: field(form, 'Submitting state'),
  successTitle: field(form, 'Success title'), successBody: field(form, 'Success body'),
  validation: field(form, 'Validation error'), serverError: field(form, 'Server error'), networkError: field(form, 'Network error'),
  rateLimit: field(form, 'Rate-limit error'), retry: '← Try again', beta: field(section('Pilot call to action'), 'Primary button'),
};
data.Gv.sectionLabel = data.Gv.sectionLabel.replaceAll('WHAT DRAFTLY DOESz', 'WHAT DRAFTLY DOES');
data.L3.secondaryHref = '/lab';
// The original overview button targeted a nonexistent #features element.
data.sE.columns[0].links[0].target = 'use-cases';
data.sE.columns[1].links[1].href = '/lab';
data.sE.columns[1].links[2].href = '/#get-started';
// serve.mjs does not publish the legal pages. Drop their footer column so Next
// never renders or prefetches the unavailable routes.
data.sE.columns = data.sE.columns.filter((column) => column.title !== 'Legal');
data.sE.copyrightLines = data.sE.copyrightLines.map((line) => line.replaceAll('\u00c2\u00a9', '\u00a9'));
const getters = Object.keys(data).map((key) => `${JSON.stringify(key)}:()=>copy[${JSON.stringify(key)}]`).join(',');
const updatedFactory = `(e,t,a)=>{const copy=${JSON.stringify(data)};a.d(t,{${getters}})}`;
fs.writeFileSync(copyFile, shared.source.replace(shared.modules[9941].toString(), updatedFactory));

const formFile = find(chunks, '84-');
const originalForm = capture(formFile);
const compiled = ts.transpileModule(fs.readFileSync(path.join(root, 'pilot-form.ts'), 'utf8'), {
  compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS },
}).outputText.replaceAll('require("react")', 'require(2132)');
const formFactory = `(module,exports,require)=>{${compiled}\nconst PilotForm=createPilotForm(require(9941).L3.form);require.d(exports,{t:()=>PilotForm});}`;
fs.writeFileSync(formFile, originalForm.source.replace(originalForm.modules[1668].toString(), formFactory));
const pageFile = find(path.join(chunks, 'app/(app)'), 'page-');
let page = fs.readFileSync(pageFile, 'utf8');
page = page.replace('(0,t.jsx)(xH.t,{align:"center"})', '(0,t.jsx)(xH.t,{align:"center",beta:true})');
page = page.replace(/"(?:[^"\\]|\\.)*"/g, (token) => {
  let value;
  try { value = JSON.parse(token); } catch { value = vm.runInNewContext(token); }
  return typeof value === 'string' && value.startsWith('Security at SAMMY Labs') ? JSON.stringify(field(section('Trust and review'), 'Trust link')) : token;
});
fs.writeFileSync(pageFile, page);

// Keep the existing animated Lady Justice treatment, but replace the copied
// foreign-regulation source text that it types with Draftly's own safe demo
// operations. The surrounding animation code is deliberately untouched.
const heroFile = find(chunks, '697-');
let hero = fs.readFileSync(heroFile, 'utf8');
const heroOperations = [
  'draftly.review({ source: "deed", page: 3, status: "needs_review" })',
  'draftly.compare({ deed: "prior", plan: "survey", field: "boundary" })',
  'draftly.trace({ instrument: "transfer", source: "registry_record" })',
  'draftly.retrieve({ jurisdiction: "Sri_Lanka", sources: ["statute", "case_law"] })',
  'draftly.verify({ fact: "property_extent", reviewer: "lawyer" })',
  'draftly.prepare({ output: "title_report", approval: "required" })',
].join('');
const heroPattern = /,u='(?:[^'\\]|\\.)*',s=\[/;
if (heroPattern.test(hero)) {
  hero = hero.replace(heroPattern, `,u=${JSON.stringify(heroOperations)},s=[`);
} else if (!hero.includes('draftly.review({ source:')) {
  throw new Error('Could not locate the Lady Justice animation source string.');
}
fs.writeFileSync(heroFile, hero);
const layoutFile = find(path.join(chunks, 'app'), 'layout-');
const layout = fs.readFileSync(layoutFile, 'utf8')
  .replace('href:"/#get-started",onClick:()=>t(!1)', 'href:"/app",onClick:()=>t(!1)')
  .replace('href:"/app",onClick:()=>t(!1)', 'href:"/app",prefetch:false,onClick:()=>t(!1)')
  .replace(
    '(0,a.jsx)(o.default,{src:"/logo_raw.svg",alt:"Draftly",width:90,height:14,className:"w-auto h-[14px] transition-[filter] duration-300 ".concat(l?"brightness-0 invert":"brightness-0")})',
    '(0,a.jsx)("span",{className:"text-[16px] font-semibold tracking-[0.12em] transition-colors duration-300 ".concat(l?"text-white/85":"text-[#141314]/85"),style:j,children:"Draftly"})',
  )
  .replace(
    '(0,a.jsx)(o.default,{src:"/logo_raw.svg",alt:"Draftly",width:90,height:12,className:"w-auto h-[12px] transition-[filter] duration-300 ".concat(l?"brightness-0 invert":"brightness-0")})',
    '(0,a.jsx)("span",{className:"text-[14px] font-semibold tracking-[0.12em] transition-colors duration-300 ".concat(l?"text-white/85":"text-[#141314]/85"),style:j,children:"Draftly"})',
  );
fs.writeFileSync(layoutFile, layout);
// A browser-saved deployment cannot hydrate its already rendered DOM reliably.
// Use Next's supported client-root rendering path for this standalone mirror.
const bootFile = find(chunks, '116-');
const boot = fs.readFileSync(bootFile, 'utf8').replace('i.default.hydrateRoot(R,r,{...N,formState:j})', 'i.default.createRoot(R,N).render(r)');
fs.writeFileSync(bootFile, boot);

// Nav links are full page loads in this saved deployment, so the nav intro
// replayed on every page. After the first page in a tab, skip to its finished
// state. React resets <html> attributes when it mounts but keeps head styles.
const navIntroScript = "try{if(sessionStorage.getItem('draftly-nav-intro')){const s=document.createElement('style');s.textContent='.fixed.top-0.left-0.right-0 *{animation-delay:0s!important;animation-duration:0s!important}';document.head.appendChild(s)}else sessionStorage.setItem('draftly-nav-intro','seen')}catch{}";
// Synchronize the existing metadata in the serialized React stream as well.
for (const relative of ['index.html', 'lab/index.html']) {
  const file = path.join(host, relative);
  const $ = cheerio.load(fs.readFileSync(file, 'utf8'));
  const pushes = [];
  $('script').each((_, element) => {
    const match = ($(element).html() ?? '').match(/^self\.__next_f\.push\(([^]*)\)$/);
    if (match) { const args = JSON.parse(match[1]); if (args[0] === 1) pushes.push({ element, text: args[1] }); }
  });
  const stream = Buffer.from(pushes.map((push) => push.text).join(''));
  let cursor = 0;
  let result = '';
  while (cursor < stream.length) {
    const colon = stream.indexOf(58, cursor);
    if (stream[colon + 1] === 84) {
      const comma = stream.indexOf(44, colon + 2);
      const length = parseInt(stream.subarray(colon + 2, comma).toString(), 16);
      const end = comma + 1 + length;
      result += stream.subarray(cursor, end).toString(); cursor = end;
    } else {
      const end = stream.indexOf(10, colon + 1) + 1;
      if (!end) throw new Error('Incomplete React stream');
      let row = stream.subarray(cursor, end).toString();
      row = row.replace(/"(?:[^"\\]|\\.)*"/g, (token) => {
        const value = JSON.parse(token);
        if (/^(?:SAMMY Labs|Draftly) — Deterministic, interpretable legal/.test(value)) return JSON.stringify(field(section('Page metadata'), 'Title'));
        return token;
      });
      result += row; cursor = end;
    }
  }
  pushes.forEach((push, index) => $(push.element).text(`self.__next_f.push(${JSON.stringify([1, index === 0 ? result : ''])})`));
  $('title').text(field(section('Page metadata'), 'Title'));
  $('script[src="/draftly-fixes.js"]').remove();
  $('body').append('<script src="/draftly-fixes.js" defer></script>');
  // Runs in <head> so it applies before the nav's first paint.
  $('#draftly-nav-intro').remove();
  $('head').append(`<script id="draftly-nav-intro">${navIntroScript}</script>`);
  fs.writeFileSync(file, $.html());
}
fs.copyFileSync(path.join(root, 'draftly-fixes.js'), path.join(host, 'draftly-fixes.js'));
fs.copyFileSync(path.join(root, 'draftly-favicon.svg'), path.join(host, 'draftly-favicon.svg'));
const cssFile = find(path.join(chunks, '../css'), '7d572');
const css = fs.readFileSync(cssFile, 'utf8');
if (!css.includes('/* Draftly keyboard focus */')) fs.appendFileSync(cssFile, '\n/* Draftly keyboard focus */\na:focus-visible,button:focus-visible,input:focus-visible{outline:2px solid #176b75!important;outline-offset:3px!important}\n');
// The open mobile menu disables pointer events outside itself, which left the
// visible Draftly logo above it unable to take a tap.
if (!css.includes('/* Draftly nav logo */')) fs.appendFileSync(cssFile, '\n/* Draftly nav logo */\n.fixed.top-0.left-0.right-0 nav a[href="/"]{pointer-events:auto}\n');
// This existing shared chunk registers all four legal-page chunk IDs.
const legalChunk = find(path.join(chunks, 'app/(app)/terms'), 'page-');
for (const route of ['dpa', 'security', 'service-description']) {
  const directory = path.join(chunks, 'app/(app)', route);
  fs.mkdirSync(directory, { recursive: true });
  fs.copyFileSync(legalChunk, path.join(directory, path.basename(legalChunk)));
}
for (const route of ['privacy-policy', 'terms', 'dpa', 'subprocessors', 'security', 'service-description']) {
  const file = path.join(host, route, 'index.html');
  const $ = cheerio.load(fs.readFileSync(file, 'utf8'));
  if (!$('link[rel="icon"]').length) $('head').append('<link rel="icon" href="/icon.png?4888f70e48b8b565" type="image/png">');
  fs.writeFileSync(file, $.html());
}
console.log('Applied in-place landing-page audit fixes.');
