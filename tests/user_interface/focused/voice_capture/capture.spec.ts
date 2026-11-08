import { test, expect } from '../../../../apps/frontend/node_modules/@playwright/test';

test('streams only during a held key and stops on release and blur', async ({ page }) => {
  const messages: (string | Buffer)[] = [];
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.routeWebSocket('**/api/v1/audio', ws => {
    ws.send(JSON.stringify({ type: 'ready', session_id: 'test-session' }));
    ws.onMessage(message => {
      messages.push(message);
      if (message === 'stop') ws.send(JSON.stringify({ type: 'paused', audio_bytes: 256 }));
    });
  });
  await page.goto('/');
  await page.getByRole('button', { name: 'Start session' }).click();
  await expect(page.getByText('Connected · microphone off', { exact: true })).toBeVisible();
  expect(messages.filter(Buffer.isBuffer)).toHaveLength(0);
  await page.locator('h1').click();
  await page.keyboard.down('Space');
  await expect(page.getByText('Microphone live', { exact: true })).toBeVisible();
  await expect.poll(() => messages.filter(Buffer.isBuffer).length).toBeGreaterThan(0);
  await page.keyboard.up('Space');
  await expect(page.getByText('Connected · microphone off', { exact: true })).toBeVisible();
  await expect.poll(() => messages.includes('stop')).toBe(true);
  await page.keyboard.down('Space');
  await expect(page.getByText('Microphone live', { exact: true })).toBeVisible();
  await page.evaluate(() => window.dispatchEvent(new Event('blur')));
  await expect(page.getByText('Connected · microphone off', { exact: true })).toBeVisible();
  await page.keyboard.up('Space');
  await page.getByRole('button', { name: 'End session' }).click();
  await expect(page.getByText('No active session', { exact: true })).toBeVisible();
  // No audio may follow a stop until the next start.
  let active = false;
  for (const message of messages) {
    if (message === 'start') active = true;
    else if (message === 'stop') active = false;
    else if (Buffer.isBuffer(message)) expect(active).toBe(true);
  }
  expect(errors).toEqual([]);
});

test('permission denial leaves microphone off with a recoverable error', async ({ page }) => {
  await page.addInitScript(() => {
    navigator.mediaDevices.getUserMedia = () => Promise.reject(new DOMException('Denied', 'NotAllowedError'));
  });
  await page.routeWebSocket('**/api/v1/audio', ws => ws.send(JSON.stringify({ type: 'ready' })));
  await page.goto('/');
  await page.getByRole('button', { name: 'Start session' }).click();
  await expect(page.getByRole('button', { name: 'End session' })).toBeVisible();
  await page.locator('h1').click();
  await page.keyboard.down('Space');
  await expect(page.getByRole('alert')).toContainText('Microphone unavailable');
  await expect(page.getByText('Connected · microphone off', { exact: true })).toBeVisible();
  await page.keyboard.up('Space');
});

test('desktop and narrow layouts fit the viewport', async ({ page }) => {
  await page.goto('/');
  for (const width of [1440, 390]) {
    await page.setViewportSize({ width, height: 1000 });
    await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.screenshot({ path: `test-results/voice-${width}.png`, fullPage: true });
  }
});

test('release before permission resolves never transmits audio', async ({ page }) => {
  const messages: (string | Buffer)[] = [];
  await page.addInitScript(() => {
    const original = navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);
    Object.assign(window, { allowMicrophone: () => {} });
    navigator.mediaDevices.getUserMedia = constraints => new Promise(resolve => {
      Object.assign(window, { allowMicrophone: () => original(constraints).then(resolve) });
    });
  });
  await page.routeWebSocket('**/api/v1/audio', ws => {
    ws.send(JSON.stringify({ type: 'ready' }));
    ws.onMessage(message => messages.push(message));
  });
  await page.goto('/');
  await page.getByRole('button', { name: 'Start session' }).click();
  await expect(page.getByRole('button', { name: 'End session' })).toBeVisible();
  await page.locator('h1').click();
  await page.keyboard.down('Space');
  await page.keyboard.up('Space');
  await page.evaluate(async () => {
    await (window as unknown as { allowMicrophone: () => Promise<void> }).allowMicrophone();
  });
  await expect(page.getByText('Connected · microphone off', { exact: true })).toBeVisible();
  expect(messages).not.toContain('start');
  expect(messages.filter(Buffer.isBuffer)).toHaveLength(0);
});
