import { TestBed } from '@angular/core/testing';
import { describe, it, expect, vi } from 'vitest';
import { AppComponent } from './app';
import { AudioSession } from './audio-session';

describe('Push-to-talk keyboard controls', () => {
  function create() {
    TestBed.configureTestingModule({});
    const app = TestBed.runInInjectionContext(() => new AppComponent());
    const audio = TestBed.inject(AudioSession);
    return { app, press: vi.spyOn(audio, 'press').mockResolvedValue(), release: vi.spyOn(audio, 'release') };
  }

  it('starts only for Space and ignores repeated or modified presses', () => {
    const { app, press } = create();
    app.keydown(new KeyboardEvent('keydown', { code: 'Enter' }));
    app.keydown(new KeyboardEvent('keydown', { code: 'Space', repeat: true }));
    app.keydown(new KeyboardEvent('keydown', { code: 'Space', ctrlKey: true }));
    expect(press).not.toHaveBeenCalled();
    app.keydown(new KeyboardEvent('keydown', { code: 'Space' }));
    expect(press).toHaveBeenCalledOnce();
  });

  it('stops on Space release and focus loss', () => {
    const { app, release } = create();
    app.keyup(new KeyboardEvent('keyup', { code: 'Enter' }));
    expect(release).not.toHaveBeenCalled();
    app.keyup(new KeyboardEvent('keyup', { code: 'Space' }));
    app.blur();
    expect(release).toHaveBeenCalledTimes(2);
  });
});
