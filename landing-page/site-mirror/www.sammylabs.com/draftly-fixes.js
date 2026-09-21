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

  function applyFixes() {
    sanitizeText(document.body);
    fixHeroIntroduction();
    replaceCoverageMap();
    fixAnchors();
    removeUnavailableLinks();
  }

  const style = document.createElement('style');
  style.textContent = `
    .draftly-intro-panel {
      background: #f4f1e9 !important;
      border-left: 4px solid #ff4002;
      color: #141314 !important;
      padding: 18px 22px;
      max-width: 46rem !important;
    }
    .draftly-intro-panel p { color: #141314 !important; }
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
  applyFixes();
  for (const delay of [100, 500, 1500, 3000]) setTimeout(applyFixes, delay);
})();
