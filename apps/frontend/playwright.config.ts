import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: '../../tests/user_interface/focused/voice_capture',
  outputDir: 'test-results',
  use: {
    baseURL: 'http://localhost:4200',
    permissions: ['microphone'],
    launchOptions: { args: ['--use-fake-device-for-media-stream', '--use-fake-ui-for-media-stream'] },
  },
  webServer: { command: 'npm start', url: 'http://localhost:4200', reuseExistingServer: true },
});
