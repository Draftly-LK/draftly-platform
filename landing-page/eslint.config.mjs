import { createRequire } from 'node:module';
const require = createRequire(new URL('../frontend/package.json', import.meta.url));
const js = require('@eslint/js');
const parser = require('@typescript-eslint/parser');
const ts = require('@typescript-eslint/eslint-plugin');
export default [
  { ignores: ['node_modules/**', 'site-mirror/**'] },
  { ...js.configs.recommended, files: ['*.mjs'], languageOptions: { globals: { process: 'readonly', Buffer: 'readonly', URL: 'readonly', URLSearchParams: 'readonly', console: 'readonly' } } },
  { files: ['verify-rendered.mjs'], languageOptions: { globals: { document: 'readonly', setTimeout: 'readonly' } } },
  { files: ['*.ts'], languageOptions: { parser, globals: { fetch: 'readonly', requestAnimationFrame: 'readonly' } }, plugins: { '@typescript-eslint': ts }, rules: { ...ts.configs.recommended.rules, 'no-unused-vars': 'off' } },
];
