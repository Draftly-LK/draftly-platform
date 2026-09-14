import path from 'node:path';
import { fileURLToPath } from 'node:url';
import scrape from 'website-scraper';
import defaultOptions from 'website-scraper/defaultOptions';

const projectDirectory = path.dirname(fileURLToPath(import.meta.url));
const outputName = process.argv[2] ?? 'site-mirror';
if (!/^[a-zA-Z0-9_-]+$/.test(outputName)) {
  throw new Error('Output directory must be a simple name containing letters, numbers, - or _.');
}
const outputDirectory = path.join(projectDirectory, outputName);
const allowedHosts = new Set([
  'sammylabs.com',
  'www.sammylabs.com',
  'api.fontshare.com',
  'cdn.fontshare.com',
  'fonts.googleapis.com',
  'fonts.gstatic.com',
]);

const extraSources = [
  { selector: 'meta[property="og:image"]', attr: 'content' },
  { selector: 'meta[name="twitter:image"]', attr: 'content' },
  { selector: 'video', attr: 'src' },
  { selector: 'video source', attr: 'src' },
  { selector: 'audio', attr: 'src' },
  { selector: 'audio source', attr: 'src' },
  { selector: 'object', attr: 'data' },
];

const isAllowedUrl = (value) => {
  const url = new URL(value);
  return allowedHosts.has(url.hostname);
};

console.log(`Mirroring https://www.sammylabs.com/ into ${outputDirectory}`);

const resources = await scrape({
  urls: [
    'https://www.sammylabs.com/',
    'https://www.sammylabs.com/lady-justice-v5.html',
    'https://www.sammylabs.com/gavel-ascii.json',
  ],
  directory: outputDirectory,
  recursive: true,
  maxRecursiveDepth: 10,
  filenameGenerator: 'bySiteStructure',
  prettifyUrls: true,
  ignoreErrors: true,
  requestConcurrency: 6,
  urlFilter: isAllowedUrl,
  sources: [...defaultOptions.sources, ...extraSources],
  request: {
    headers: {
      'user-agent':
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 ' +
        '(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    },
    retry: { limit: 2 },
    timeout: { request: 30000 },
  },
});

console.log(`Saved ${resources.length} top-level resource tree(s).`);
console.log('Mirror complete. Run `npm run serve` and open http://localhost:4173/.');
