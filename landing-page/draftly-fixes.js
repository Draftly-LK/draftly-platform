(() => {
  const replacements = new Map([
    ['Ã¢â‚¬â„¢', '’'], ['â€™', '’'],
    ['Ã¢â‚¬â€', '—'], ['â€”', '—'],
    ['Ã¢â‚¬Å“', '“'], ['â€œ', '“'],
    ['Ã¢â‚¬Â', '”'], ['â€', '”'],
    ['Ã¢â‚¬Â¦', '…'], ['â€¦', '…'],
    ['Ã‚Â·', '·'], ['Â·', '·'],
    ['Ã‚Â©', '©'], ['Â©', '©'],
    ['Ãƒâ€”', '×'], ['Ã—', '×'],
  ]);
  const deniedBrands = /\bSAMMY Labs\b|\bSAMMY AI\b|\bSAMMY\b/gi;
  const unavailableRoutes = new Set([
    'ascii-letter', 'ascii-magnifying-glass', 'ascii-phone', 'ascii-policies',
    'ascii-radar', 'careers', 'dpa', 'lady-justice-v5', 'lady-justice-v6',
    'privacy-policy', 'regulators', 'security', 'service-description',
    'subprocessors', 'terms',
  ]);

  function cleanText(value) {
    let output = value;
    for (const [broken, clean] of replacements) output = output.replaceAll(broken, clean);
    // A middle dot was lost from the labels' separators and left a bare "?".
    if (output === ' ? ' || /^[A-Za-z][A-Za-z -]+( \? [A-Za-z][A-Za-z -]+)+$/.test(output.trim())) output = output.replaceAll(' ? ', ' · ');
    return output
      .replace(deniedBrands, 'Draftly')
      .replace(/Source\s*·\s*Draftly corpus\s*·\s*Updated in real-time/gi, 'Source · Draftly research corpus · Current snapshot');
  }

  function sanitizeText(root) {
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    const nodes = [];
    while (walker.nextNode()) nodes.push(walker.currentNode);
    for (const node of nodes) {
      if (node.parentElement?.closest('script,style,noscript')) continue;
      const clean = cleanText(node.nodeValue ?? '');
      if (clean !== node.nodeValue) node.nodeValue = clean;
    }
  }

  function fixHeroIntroduction() {
    const paragraph = [...document.querySelectorAll('p')].find((element) =>
      element.textContent?.trim().startsWith('Draftly helps lawyers process conveyancing matters'),
    );
    paragraph?.parentElement?.classList.add('draftly-intro-panel');
  }

  function replaceCoverageMap() {
    const label = [...document.querySelectorAll('span')].find((element) =>
      /global regulatory coverage/i.test(element.textContent ?? ''),
    );
    const root = label?.closest('.relative.w-full');
    if (!root || root.hasAttribute('data-draftly-scope')) return;
    root.setAttribute('data-draftly-scope', 'true');
    root.innerHTML = `
      <div class="draftly-scope-grid" aria-label="Current Draftly scope">
        <div><span>Practice area</span><strong>Conveyancing and title review</strong></div>
        <div><span>Jurisdiction</span><strong>Sri Lanka</strong></div>
        <div><span>Document languages</span><strong>Sinhala · Tamil · English</strong></div>
        <div><span>Pilot status</span><strong>Research and practitioner evaluation</strong></div>
      </div>
      <p class="draftly-scope-note">Availability varies by document type and workflow stage during development. These figures describe the research corpus, not complete legal coverage.</p>`;
  }

  const statusIcons = {
    verified: '<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true"><circle cx="8" cy="8" r="6.25"/><path d="m5.25 8.2 1.9 1.9 3.6-3.9" stroke-linecap="round" stroke-linejoin="round"/></svg>',
    review: '<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true"><path d="M8 1.9 14.4 13H1.6L8 1.9Z" stroke-linejoin="round"/><path d="M8 6.4v3M8 11.3v.1" stroke-linecap="round"/></svg>',
    missing: '<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true"><circle cx="8" cy="8" r="6.25" stroke-dasharray="2.2 2"/><path d="M5.5 8h5" stroke-linecap="round"/></svg>',
  };

  // The workspace mock-up was a cycling demo for another product and
  // jurisdiction. Hide it and show a static, clearly labelled sample instead.
  function replaceWorkspaceMock() {
    for (const frame of document.querySelectorAll('div.w-full.rounded-lg.overflow-hidden.border.border-neutral-200:not([data-draftly-mock])')) {
      if (!/Reg Z|CFPB|Portfolio Accounts|Traversing ontology|LN-\d/.test(frame.textContent ?? '')) continue;
      frame.setAttribute('data-draftly-mock', 'true');
      const rows = [
        ['Deed of transfer', 'Deed', 'Sinhala', 'verified', 'Verified'],
        ['Survey plan', 'Plan', 'English', 'review', 'Needs review'],
        ['Registry extract', 'Registry record', 'English', 'verified', 'Verified'],
        ['Assessment notice', 'Assessment', 'Sinhala', 'review', 'Needs review'],
        ['Earlier title deed', 'Deed', 'Not yet provided', 'missing', 'Missing'],
      ].map(([name, type, language, state, label]) => `
        <tr>
          <th scope="row">${name}</th><td>${type}</td><td>${language}</td>
          <td><span class="draftly-status draftly-status--${state}">${statusIcons[state]}${label}</span></td>
        </tr>`).join('');
      const panel = document.createElement('div');
      panel.className = 'draftly-mock';
      panel.setAttribute('role', 'group');
      panel.setAttribute('aria-label', 'Sample matter workspace');
      panel.innerHTML = `
        <div class="draftly-mock__bar"><span>Matter workspace</span><span>Sample data</span></div>
        <div class="draftly-mock__body">
          <table>
            <caption class="draftly-sr">Documents in the sample matter and their review status</caption>
            <thead><tr><th scope="col">Document</th><th scope="col">Type</th><th scope="col">Language</th><th scope="col">Status</th></tr></thead>
            <tbody>${rows}</tbody>
          </table>
          <div class="draftly-mock__fact">
            <span class="draftly-mock__label">Proposed fact</span>
            <strong>Transferor name</strong>
            <dl>
              <div><dt>Source</dt><dd>Deed of transfer, page 2</dd></div>
              <div><dt>Status</dt><dd><span class="draftly-status draftly-status--review">${statusIcons.review}Awaiting lawyer decision</span></dd></div>
            </dl>
            <p>Accept, correct or reject each value. The link to the original page stays attached.</p>
          </div>
        </div>
        <div class="draftly-mock__foot">Illustrative sample. Not a real matter.</div>`;
      frame.appendChild(panel);
    }
  }

  // A sentence ending runs straight into the next inline element.
  function fixSentenceSpacing() {
    for (const node of document.querySelectorAll('p')) {
      for (const child of node.childNodes) {
        if (child.nodeType === Node.TEXT_NODE && child.nodeValue.endsWith('validated.') && child.nextSibling) child.nodeValue += ' ';
      }
    }
  }

  // Contrast helpers: the copy uses translucent and brand-orange text that
  // misses WCAG AA on several sections. Only a fixed selector list is checked
  // (never the hero animation's thousands of nodes). Scroll effects rewrite
  // some inline colours, so it is re-run on each throttled scroll tick.
  function channels(value) {
    const [r, g, b, a = 1] = (value.match(/[\d.]+/g) ?? [0, 0, 0]).map(Number);
    return { r, g, b, a };
  }
  function luminance({ r, g, b }) {
    const lin = (v) => { const c = v / 255; return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4; };
    return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
  }
  function backdropOf(element) {
    const layers = [];
    for (let node = element; node; node = node.parentElement) {
      const layer = channels(getComputedStyle(node).backgroundColor);
      if (layer.a > 0) { layers.push(layer); if (layer.a >= 1) break; }
    }
    return layers.reverse().reduce((base, layer) => ({
      r: base.r * (1 - layer.a) + layer.r * layer.a,
      g: base.g * (1 - layer.a) + layer.g * layer.a,
      b: base.b * (1 - layer.a) + layer.b * layer.a,
    }), { r: 255, g: 255, b: 255 });
  }
  function raiseContrast() {
    const candidates = document.querySelectorAll('.text-brand-orange, .section-label, p[style*="color"], .font-jetbrains[style*="color"], [class*="text-muted"], [class*="text-neutral-"], [class*="text-white/"], [class*="text-slate-"], [class*="uppercase"][class*="font-mono"], [class*="/40"], [class*="/50"], [class*="/60"]');
    for (const element of candidates) {
      if (element.closest('.draftly-mock, .bg-brand-orange') || !element.textContent?.trim()) continue;
      const style = getComputedStyle(element);
      const backdrop = backdropOf(element);
      const fg = channels(style.color);
      const shown = {
        r: backdrop.r * (1 - fg.a) + fg.r * fg.a,
        g: backdrop.g * (1 - fg.a) + fg.g * fg.a,
        b: backdrop.b * (1 - fg.a) + fg.b * fg.a,
      };
      const [light, dark] = [luminance(shown), luminance(backdrop)].sort((x, y) => y - x);
      const size = parseFloat(style.fontSize);
      const needed = size >= 24 || (size >= 18.66 && Number(style.fontWeight) >= 700) ? 3 : 4.5;
      if ((light + 0.05) / (dark + 0.05) >= needed) continue;
      // Light surface: use a solid AA-passing ink; dark surface: a lighter one.
      const onLight = luminance(backdrop) > 0.4;
      const isOrange = style.color === 'rgb(255, 64, 2)';
      element.style.setProperty('color', onLight ? (isOrange ? '#c2410c' : '#475569') : 'rgba(255, 255, 255, .72)', 'important');
    }
  }

  // The "compliance.rs" code window belonged to another product and quoted a
  // foreign statute. Swap in a static, structural walkthrough of the research
  // flow: no citations, quotations or figures.
  function replaceResearchMock() {
    const label = [...document.querySelectorAll('span')].find((element) => element.childElementCount === 0 && element.textContent.trim() === 'compliance.rs');
    const frame = label?.closest('div.overflow-hidden');
    if (!frame || frame.hasAttribute('data-draftly-mock')) return;
    frame.setAttribute('data-draftly-mock', 'true');
    const steps = [
      ['Question', 'A conveyancing scenario is entered in plain language.'],
      ['Retrieval', 'Related enactments and case law are retrieved together.'],
      ['Citation', 'Each answer keeps its enactment, section and source text.'],
      ['Review', 'Findings stay proposed until a lawyer has reviewed them.'],
    ].map(([title, text]) => `<li><strong>${title}</strong><span>${text}</span></li>`).join('');
    const panel = document.createElement('div');
    panel.className = 'draftly-mock';
    panel.setAttribute('role', 'group');
    panel.setAttribute('aria-label', 'Sample research flow');
    panel.innerHTML = `
      <div class="draftly-mock__bar"><span>Research flow</span><span>Sample data</span></div>
      <div class="draftly-mock__body draftly-mock__body--single"><ol class="draftly-steps">${steps}</ol></div>
      <div class="draftly-mock__foot">Illustrative sample. No real matter or authority is shown.</div>`;
    frame.appendChild(panel);
    // The hidden window keeps typing its old text; keep that text brand-safe too.
    let pending = 0;
    new MutationObserver(() => {
      if (pending) return;
      pending = setTimeout(() => { pending = 0; sanitizeText(frame); }, 100);
    }).observe(frame, { childList: true, subtree: true, characterData: true });
    sanitizeText(frame);
  }

  // Every chip in a card once carried the same joined label, followed by a
  // leftover "+N" count. Split the label into one chip per item instead.
  function fixLabelChips() {
    const isBadge = (chip) => /^\+\d+$/.test(chip.textContent.trim());
    for (const row of document.querySelectorAll('div.flex.flex-wrap.gap-1\\.5')) {
      const chips = [...row.children];
      const joined = chips.find((chip) => /[·Â]/.test(chip.textContent));
      if (joined) {
        const items = joined.textContent.split(/\s*[·Â]+\s*/).map((item) => item.trim()).filter(Boolean);
        if (items.length < 2) continue;
        row.replaceChildren(...items.map((item) => {
          const chip = joined.cloneNode(false);
          chip.textContent = item.charAt(0).toUpperCase() + item.slice(1);
          return chip;
        }));
        row.setAttribute('data-draftly-chips', 'true');
      } else if (row.hasAttribute('data-draftly-chips') || chips.some(isBadge)) {
        // Already-split chips that repeat, plus a meaningless leftover "+N".
        const seen = new Set();
        for (const chip of chips) {
          const text = chip.textContent.trim();
          if (isBadge(chip) || seen.has(text)) chip.remove();
          else seen.add(text);
        }
        row.setAttribute('data-draftly-chips', 'true');
      }
    }
  }

  function fixAnchors() {
    for (const id of ['use-cases', 'industries', 'research', 'security', 'get-started']) {
      const target = document.getElementById(id);
      if (target) target.style.scrollMarginTop = '96px';
    }
  }

  function removeUnavailableLinks() {
    for (const link of document.querySelectorAll('a[href]')) {
      let url;
      try { url = new URL(link.href, window.location.href); } catch { continue; }
      if (url.origin !== window.location.origin) continue;
      const segment = url.pathname.split('/').filter(Boolean)[0];
      if (!unavailableRoutes.has(segment)) continue;
      const listItem = link.closest('li');
      if (listItem) listItem.remove();
      else link.remove();
    }

    for (const list of document.querySelectorAll('footer ul')) {
      if (list.children.length) continue;
      const group = list.parentElement;
      if (group && group !== document.querySelector('footer')) group.remove();
    }
  }

  function fixMetadata() {
    document.title = 'Draftly — Research-backed legal technology for Sri Lankan conveyancing';
    document.documentElement.lang = 'en';
    document.querySelectorAll('link[rel="canonical"], link[rel="icon"], link[rel="apple-touch-icon"], meta[property^="og:"], meta[name^="twitter:"], script[type="application/ld+json"]').forEach((element) => element.remove());
    const description = document.querySelector('meta[name="description"]') ?? document.head.appendChild(document.createElement('meta'));
    description.setAttribute('name', 'description');
    description.setAttribute('content', 'Draftly helps Sri Lankan lawyers turn deeds, plans and registry records into a source-linked, review-ready conveyancing matter.');
    const icon = document.createElement('link');
    icon.rel = 'icon';
    icon.type = 'image/svg+xml';
    icon.href = '/draftly-favicon.svg';
    document.head.appendChild(icon);
    const structured = document.createElement('script');
    structured.type = 'application/ld+json';
    structured.textContent = JSON.stringify({
      '@context': 'https://schema.org',
      '@type': 'SoftwareApplication',
      name: 'Draftly',
      applicationCategory: 'LegalService',
      description: 'A lawyer-in-the-loop workspace being developed for Sri Lankan conveyancing.',
      areaServed: { '@type': 'Country', name: 'Sri Lanka' },
      operatingSystem: 'Web',
    });
    document.head.appendChild(structured);
  }

  // Sections below the fold render as they scroll into view, so these cheap,
  // idempotent fixes also run (throttled) while the visitor scrolls.
  function applyLazyFixes() {
    fixLabelChips();
    replaceWorkspaceMock();
    replaceResearchMock();
    fixSentenceSpacing();
    raiseContrast();
  }

  // The hero artwork is ~130k characters of decorative code text; keep it out
  // of the accessibility tree. Runs only until found (it scans a large tree).
  let heroArtHidden = false;
  function hideHeroArt() {
    if (heroArtHidden) return;
    const main = document.querySelector('main');
    const rows = main ? [...main.querySelectorAll('div')].filter((row) => row.childElementCount > 150 && row.textContent.length === row.childElementCount) : [];
    const container = rows[0]?.parentElement;
    if (!container) return;
    container.setAttribute('aria-hidden', 'true');
    heroArtHidden = true;
  }

  function applyFixes() {
    sanitizeText(document.body);
    fixHeroIntroduction();
    hideHeroArt();
    watchCards();
    applyLazyFixes();
    replaceCoverageMap();
    fixAnchors();
    removeUnavailableLinks();
  }

  const style = document.createElement('style');
  style.textContent = `
    .draftly-intro-panel {
      background: rgba(20, 19, 20, .8) !important;
      -webkit-backdrop-filter: blur(6px);
      backdrop-filter: blur(6px);
      border: 1px solid rgba(255, 255, 255, .14);
      border-left: 4px solid #ff4002;
      color: #fff !important;
      padding: 18px 22px;
      max-width: 46rem !important;
    }
    .draftly-intro-panel p { color: rgba(255, 255, 255, .92) !important; }
    [data-draftly-mock] { height: auto !important; max-height: none !important; }
    [data-draftly-mock] > :not(.draftly-mock) { display: none !important; }
    .draftly-mock { background: #fff; color: #141314; min-height: 440px; display: flex; flex-direction: column; font: 400 14px/1.45 var(--font-satoshi, system-ui, sans-serif); }
    .draftly-mock__bar, .draftly-mock__foot { display: flex; justify-content: space-between; gap: 12px; padding: 10px 16px; font: 500 11px/1.4 ui-monospace, monospace; letter-spacing: .06em; text-transform: uppercase; color: #475569; background: #f8f8f6; }
    .draftly-mock__bar { border-bottom: 1px solid #e5e5e5; }
    .draftly-mock__foot { border-top: 1px solid #e5e5e5; text-transform: none; letter-spacing: 0; margin-top: auto; }
    .draftly-mock__body { display: grid; grid-template-columns: minmax(0, 1.7fr) minmax(0, 1fr); gap: 20px; padding: 16px; flex: 1; }
    .draftly-mock table { width: 100%; border-collapse: collapse; font-size: 13px; }
    .draftly-mock th, .draftly-mock td { text-align: left; padding: 10px 8px; border-bottom: 1px solid #ececec; vertical-align: middle; }
    .draftly-mock thead th { font: 600 11px/1.4 ui-monospace, monospace; letter-spacing: .06em; text-transform: uppercase; color: #475569; }
    .draftly-mock tbody th { font-weight: 600; }
    .draftly-status { display: inline-flex; align-items: center; gap: 6px; font-weight: 600; white-space: nowrap; }
    .draftly-status--verified { color: #0f6a3a; }
    .draftly-status--review { color: #8a4b00; }
    .draftly-status--missing { color: #475569; }
    .draftly-mock__fact { border: 1px solid #e5e5e5; border-left: 3px solid #ff4002; border-radius: 6px; padding: 14px; display: flex; flex-direction: column; gap: 8px; align-self: start; }
    .draftly-mock__label { font: 600 11px/1.4 ui-monospace, monospace; letter-spacing: .06em; text-transform: uppercase; color: #475569; }
    .draftly-mock__fact strong { font-size: 16px; }
    .draftly-mock dl { margin: 0; display: grid; gap: 6px; }
    .draftly-mock dl div { display: grid; gap: 2px; }
    .draftly-mock dt { font-size: 12px; color: #475569; }
    .draftly-mock dd { margin: 0; font-weight: 500; }
    .draftly-mock__fact p { margin: 0; font-size: 13px; color: #475569; }
    .draftly-mock__body--single { grid-template-columns: 1fr; align-content: start; }
    .draftly-steps { list-style: none; margin: 0; padding: 0; display: grid; gap: 0; counter-reset: step; }
    .draftly-steps li { counter-increment: step; display: grid; grid-template-columns: 28px 1fr; column-gap: 12px; padding: 14px 0; border-bottom: 1px solid #ececec; }
    .draftly-steps li:last-child { border-bottom: 0; }
    .draftly-steps li::before { content: counter(step); grid-row: span 2; width: 24px; height: 24px; border: 1px solid #cbd5e1; border-radius: 50%; display: grid; place-items: center; font: 600 12px/1 ui-monospace, monospace; color: #475569; }
    .draftly-steps strong { font-size: 15px; }
    .draftly-steps span { color: #475569; font-size: 14px; }
    .draftly-sr { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; }
    @media (max-width: 800px) {
      .draftly-mock__body { grid-template-columns: 1fr; }
      .draftly-mock table, .draftly-mock tbody { display: block; }
      .draftly-mock thead { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); }
      .draftly-mock tr { display: grid; grid-template-columns: auto auto 1fr; column-gap: 8px; row-gap: 2px; padding: 10px 0; border-bottom: 1px solid #ececec; }
      .draftly-mock tr th, .draftly-mock tr td { padding: 0; border: 0; }
      .draftly-mock tbody th { grid-column: 1 / 3; grid-row: 1; }
      .draftly-mock tr td:nth-child(4) { grid-column: 3; grid-row: 1; justify-self: end; }
      .draftly-mock tr td:nth-child(2), .draftly-mock tr td:nth-child(3) { grid-row: 2; font-size: 12px; color: #475569; }
      .draftly-mock tr td:nth-child(2) { grid-column: 1; }
      .draftly-mock tr td:nth-child(3) { grid-column: 2; }
      .draftly-mock tr td:nth-child(3)::before { content: "\\00b7"; margin-right: 8px; }
    }
    /* Orange marquee band: dark ink passes AA where white on brand orange does not. */
    .bg-brand-orange .text-white\\/80 { color: #141314 !important; }
    .bg-brand-orange .text-white\\/40 { color: rgba(20, 19, 20, .75) !important; }
    [style*="5c6370"] { color: #9aa3b2 !important; }
    .bg-brand-orange:hover [style*="ticker"] { animation-play-state: paused !important; }
    html { scroll-padding-top: 96px; }
    [data-draftly-chips] > span { font-size: 12px !important; line-height: 1.2 !important; padding: 6px 10px !important; letter-spacing: 0; }
    /* Keep the floating nav readable when it passes over section content.
       data-draftly-nav is set from the nav's own light/dark state. */
    .fixed.top-0.left-0.right-0 nav {
      border-radius: 8px;
      -webkit-backdrop-filter: blur(10px);
      backdrop-filter: blur(10px);
      transition: background-color .2s ease;
    }
    [data-draftly-nav="light"] nav { background: rgba(255, 251, 245, .86); }
    [data-draftly-nav="dark"] nav { background: rgba(20, 19, 20, .72); }
    @media (pointer: coarse) {
      footer a, nav a, nav button { display: inline-flex; align-items: center; min-height: 44px; }
    }
    @media (prefers-reduced-motion: reduce) {
      *, *::before, *::after {
        animation-duration: .01ms !important;
        animation-iteration-count: 1 !important;
        scroll-behavior: auto !important;
        transition-duration: .01ms !important;
      }
    }
    [data-draftly-scope] { max-width: 1152px; margin-inline: auto; }
    .draftly-scope-grid {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      border: 1px solid rgba(255,255,255,.22);
    }
    .draftly-scope-grid > div {
      min-height: 150px;
      padding: 22px;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
      border-right: 1px solid rgba(255,255,255,.18);
    }
    .draftly-scope-grid > div:last-child { border-right: 0; }
    .draftly-scope-grid span {
      color: rgba(255,255,255,.55);
      font: 700 10px/1.4 ui-monospace, monospace;
      letter-spacing: .14em;
      text-transform: uppercase;
    }
    .draftly-scope-grid strong {
      color: #fff;
      font: 500 clamp(18px, 2vw, 28px)/1.15 Georgia, serif;
    }
    .draftly-scope-note { margin: 18px 0 0; color: rgba(255,255,255,.55); font-size: 13px; }
    @media (max-width: 800px) {
      .draftly-intro-panel { margin-inline: 0; padding: 16px; }
      .draftly-scope-grid { grid-template-columns: 1fr 1fr; }
      .draftly-scope-grid > div { min-height: 130px; border-bottom: 1px solid rgba(255,255,255,.18); }
      .draftly-scope-grid > div:nth-child(2) { border-right: 0; }
    }
    @media (max-width: 480px) {
      .draftly-scope-grid { grid-template-columns: 1fr; }
      .draftly-scope-grid > div { min-height: 112px; border-right: 0; }
    }
  `;
  document.head.appendChild(style);
  fixMetadata();
  // The hero animation creates thousands of changing span nodes. A persistent
  // subtree observer would rescan that animation every frame, so use a small
  // number of bounded passes around hydration instead.
  // The nav switches between light and dark treatments as it crosses sections;
  // mirror that state onto its container so the backdrop always contrasts.
  let navFrame = 0;
  function syncNavTheme() {
    navFrame = 0;
    const bar = document.querySelector('.fixed.top-0.left-0.right-0');
    const label = bar?.querySelector('nav a > span, nav span');
    if (!bar || !label) return;
    const [r, g, b] = (getComputedStyle(label).color.match(/[\d.]+/g) ?? []).map(Number);
    const luminance = (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255;
    bar.setAttribute('data-draftly-nav', luminance > 0.6 ? 'dark' : 'light');
  }
  // Switching the audience tabs (or returning to the page) makes React
  // re-render the cards from their original data, so watch that section only.
  let watched = null;
  function watchCards() {
    const tab = [...document.querySelectorAll('button')].find((button) => /Conveyancing practices/.test(button.textContent ?? ''));
    let section = tab?.parentElement ?? null;
    while (section && !section.querySelector('div.grid.grid-cols-1')) section = section.parentElement;
    if (!section || section === watched) return;
    watched = section;
    new MutationObserver(() => {
      if (lazyTimer) return;
      lazyTimer = setTimeout(() => { lazyTimer = 0; sanitizeText(section); applyLazyFixes(); }, 80);
    }).observe(section, { childList: true, subtree: true, characterData: true });
  }
  document.addEventListener('visibilitychange', () => { if (!document.hidden) { sanitizeText(document.body); applyLazyFixes(); } });
  document.addEventListener('click', () => setTimeout(() => { sanitizeText(document.body); applyLazyFixes(); }, 350), true);
  let lazyTimer = 0;
  const scheduleLazyFixes = () => {
    if (lazyTimer) return;
    lazyTimer = setTimeout(() => { lazyTimer = 0; applyLazyFixes(); sanitizeText(document.body); }, 300);
  };
  const scheduleNavSync = () => {
    if (!navFrame) navFrame = requestAnimationFrame(syncNavTheme);
    scheduleLazyFixes();
  };
  addEventListener('scroll', scheduleNavSync, { passive: true });
  addEventListener('resize', scheduleNavSync);
  applyFixes();
  // The hero renders after hydration, sometimes several seconds in, so poll
  // briefly (bounded) until the intro panel has been tagged.
  let attempts = 0;
  const poll = setInterval(() => {
    applyFixes();
    syncNavTheme();
    attempts += 1;
    if ((document.querySelector('.draftly-intro-panel') && attempts >= 6) || attempts >= 30) clearInterval(poll);
  }, 500);
})();
