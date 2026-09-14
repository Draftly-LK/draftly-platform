import path from 'node:path';
import { fileURLToPath } from 'node:url';
import scrape from 'website-scraper';
import defaultOptions from 'website-scraper/defaultOptions';
import PuppeteerPlugin from 'website-scraper-puppeteer';

const projectDirectory = path.dirname(fileURLToPath(import.meta.url));
const outputName = process.argv[2] ?? 'rendered-mirror';
if (!/^[a-zA-Z0-9_-]+$/.test(outputName)) {
  throw new Error('Output directory must be a simple name containing letters, numbers, - or _.');
}

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

const outputDirectory = path.join(projectDirectory, outputName);
console.log(`Rendering https://www.sammylabs.com/ into ${outputDirectory}`);

await scrape({
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
  requestConcurrency: 4,
  urlFilter: (value) => allowedHosts.has(new URL(value).hostname),
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
  plugins: [
    new PuppeteerPlugin({
      launchOptions: { headless: true },
      gotoOptions: { waitUntil: 'networkidle0', timeout: 60000 },
      scrollToBottom: { timeout: 12000, viewportN: 50 },
    }),
  ],
});

console.log('Browser-rendered mirror complete.');
