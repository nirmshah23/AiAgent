import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: '../../tests/user_interface/focused/dialog',
  outputDir: 'test-results/dialog',
  use: { baseURL: 'http://localhost:4211' },
  webServer: [
    { command: `${process.platform === 'win32' ? '..\\backend\\.venv\\Scripts\\python.exe' : '../backend/.venv/bin/python'} ../../tests/scripts/backend/serve_policy_test.py`, url: 'http://127.0.0.1:8011/api/v1/health' },
    { command: 'npm start -- --port 4211 --proxy-config ../../tests/scripts/user_interface/dialog-proxy.json', url: 'http://localhost:4211' },
  ],
});
