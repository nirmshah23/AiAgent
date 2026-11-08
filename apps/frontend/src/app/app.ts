import { ChangeDetectionStrategy, Component, HostListener, OnDestroy, inject } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatToolbarModule } from '@angular/material/toolbar';
import { AudioSession } from './audio-session';

@Component({
  selector: 'app-root', standalone: true,
  imports: [MatButtonModule, MatCardModule, MatToolbarModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <mat-toolbar><span class="brand">◉ Voice</span><span class="toolbar-note">Audio workspace</span></mat-toolbar>
    <main>
      <p class="eyebrow">PUSH TO TALK · ENGLISH</p>
      <h1>Your voice.<br>On your terms.</h1>
      <p class="intro">Hold the spacebar to share audio. Release it to switch your microphone off.</p>
      <mat-card appearance="outlined" class="capture-panel">
        <div class="status" aria-live="polite"><span class="dot" [class.active]="audio.recording()"></span>
          {{ audio.recording() ? 'Microphone live' : audio.connected() ? 'Connected · microphone off' : audio.connecting() ? 'Connecting…' : 'No active session' }}
        </div>
        <div class="mic" [class.live]="audio.recording()" aria-hidden="true">
          <svg viewBox="0 0 48 48"><rect x="18" y="5" width="12" height="25" rx="6"/><path d="M12 23v2a12 12 0 0 0 24 0v-2M24 37v7M17 44h14"/></svg>
        </div>
        <h2>{{ audio.recording() ? 'Listening to you' : 'Ready when you are' }}</h2>
        <p>Hold <kbd>space</kbd> to talk</p>
        <p class="hint">Audio is shared only while the key is held.</p>
        <div class="actions">
          @if (!audio.connected()) {
            <button mat-flat-button (click)="audio.connect()" [disabled]="audio.connecting()">{{ audio.connecting() ? 'Connecting…' : 'Start session' }}</button>
          } @else {
            <button mat-stroked-button (click)="audio.disconnect()">End session</button>
          }
        </div>
        @if (audio.error()) { <p class="error" role="alert">{{ audio.error() }}</p> }
      </mat-card>
      <section class="details" aria-label="How it works">
        <div><span class="step">01</span><h3>Connect</h3><p>Start a session, then hold Space to allow microphone access.</p></div>
        <div><span class="step">02</span><h3>Hold to speak</h3><p>Keep Space pressed as you speak. Release to stop capturing.</p></div>
        <div><span class="step">03</span><h3>Stay in control</h3><p>Leaving this window stops capture. End the session when finished.</p></div>
      </section>
      <footer>Audio transport preview · No spoken replies yet.<br>Session metadata is saved. Audio is streamed and discarded.</footer>
    </main>`,
})
export class AppComponent implements OnDestroy {
  readonly audio = inject(AudioSession);

  @HostListener('window:keydown', ['$event'])
  keydown(event: KeyboardEvent): void {
    if (event.code !== 'Space' || event.altKey || event.ctrlKey || event.metaKey || event.repeat) return;
    const target = event.target;
    if (target instanceof HTMLElement && target.closest('button, input, textarea, select, a, [contenteditable="true"]')) return;
    event.preventDefault();
    void this.audio.press();
  }

  @HostListener('window:keyup', ['$event'])
  keyup(event: KeyboardEvent): void {
    if (event.code === 'Space') this.audio.release();
  }
  @HostListener('window:blur') blur(): void { this.audio.release(); }
  @HostListener('document:visibilitychange') visibility(): void {
    if (document.hidden) this.audio.release();
  }
  @HostListener('window:pagehide') ngOnDestroy(): void { this.audio.disconnect(); }
}
