import path from 'node:path';
import { fileURLToPath } from 'node:url';
import puppeteer from '@website-scraper/puppeteer-version-wrapper';

const projectDirectory = path.dirname(fileURLToPath(import.meta.url));
const url = process.argv[2] ?? 'http://127.0.0.1:4174/';
const screenshotPath = path.join(projectDirectory, 'rendered-preview.png');
console.log('Launching browser');
const browser = await puppeteer.launch({ headless: true, timeout: 60000 });
console.log('Opening page');
const page = await browser.newPage();
page.setDefaultTimeout(60000);
await page.setViewport({ width: 1440, height: 900, deviceScaleFactor: 1 });

const errors = [];
page.on('pageerror', (error) => errors.push(`page: ${error.message}`));
page.on('requestfailed', (request) =>
  errors.push(`request: ${request.url()} (${request.failure()?.errorText ?? 'failed'})`),
);

await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 60000 });
console.log('Page loaded');
await new Promise((resolve) => setTimeout(resolve, 1200));
const firstMorph = await page.evaluate(() =>
  [...document.querySelectorAll('[aria-hidden="true"]')]
    .map((element) => element.textContent?.trim())
    .find((text) => text?.includes('Rule')) ?? '',
);
await new Promise((resolve) => setTimeout(resolve, 3500));
const secondMorph = await page.evaluate(() =>
  [...document.querySelectorAll('[aria-hidden="true"]')]
    .map((element) => element.textContent?.trim())
    .find((text) => text?.includes('Rule')) ?? '',
);
await page.screenshot({ path: screenshotPath, fullPage: false });

const summary = await page.evaluate(() => ({
  title: document.title,
  heading: document.querySelector('h1')?.textContent?.trim() ?? '',
  mainVisible: Boolean(document.querySelector('main, [class*="overflow-x-clip"]')),
  bodyHeight: document.body.scrollHeight,
}));

await browser.close();
console.log(JSON.stringify({ ...summary, morphChanged: firstMorph !== secondMorph, errors, screenshotPath }, null, 2));
