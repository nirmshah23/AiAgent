import { ChangeDetectionStrategy, Component, HostListener, inject, output, signal, computed } from '@angular/core';
import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { MatButtonModule } from '@angular/material/button';
import { MAT_DIALOG_DATA, MatDialog, MatDialogModule } from '@angular/material/dialog';
import { MatExpansionModule } from '@angular/material/expansion';
import { ConfigField, Json, Schema, initial } from './config-field';

interface Snapshot { configuration: { [key: string]: Json }; revision: string; json_schema: Schema }

@Component({
  selector: 'app-confirm-change', standalone: true, imports: [MatButtonModule, MatDialogModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `<h2 mat-dialog-title>{{ data.title }}</h2><mat-dialog-content>{{ data.message }}</mat-dialog-content><mat-dialog-actions align="end"><button mat-button [mat-dialog-close]="false">Cancel</button><button mat-flat-button [mat-dialog-close]="true">{{ data.action }}</button></mat-dialog-actions>`,
})
export class ConfirmChange {
  readonly data = inject<{ title: string; message: string; action: string }>(MAT_DIALOG_DATA);
}

@Component({
  selector: 'app-intent-settings', standalone: true,
  imports: [ConfigField, MatButtonModule, MatExpansionModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  styles: [`
    :host { display: block; max-width: 1280px; margin: auto; padding: 28px 24px; }
    h1 { font-size: 32px; letter-spacing: -1px; margin: 16px 0; }
    header p, .help { color: var(--mat-sys-on-surface-variant); line-height: 1.6; }
    .layout { display: grid; grid-template-columns: 260px minmax(0, 1fr); gap: 28px; margin-top: 24px; align-items: start; }
    nav { display: grid; gap: 8px; position: sticky; top: 100px; }
    nav button { height: auto; min-height: 48px; padding: 12px; justify-content: start; text-align: left; white-space: normal; overflow-wrap: anywhere; }
    .selected { background: var(--mat-sys-secondary-container); }
    .editor { min-width: 0; }
    .bar { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }
    .save-bar { position: sticky; top: 0; z-index: 2; padding: 16px 0; background: var(--mat-sys-surface); border-top: 1px solid var(--mat-sys-outline-variant); margin: 20px 0; }
    .error { padding: 12px; border: 1px solid var(--mat-sys-error); overflow-wrap: anywhere; }
    .notice { padding: 12px; background: var(--mat-sys-secondary-container); border-radius: 8px; }
    mat-expansion-panel { margin: 12px 0; }
    @media(max-width: 700px) { :host { padding: 20px 16px; } .layout { grid-template-columns: 1fr; gap: 16px; } nav { position: static; } }
  `],
  template: `
    <button mat-button (click)="requestClose()" [disabled]="busy()">Back to voice</button>
    <header><p class="eyebrow">DIALOG CONFIGURATION</p><h1>Intent settings</h1><p>Configure what the assistant recognizes, the information it needs, and how it responds.</p></header>
    @if (error()) { <div class="error" role="alert">{{ error() }}</div> }
    @if (message()) { <p class="notice" role="status">{{ message() }}</p> }
    @if (loading()) { <p role="status">Loading configuration…</p> }
    @if (!snapshot() && !loading()) { <button mat-stroked-button (click)="load()">Retry loading</button> }
    @if (snapshot(); as data) {
      <p class="help">Changes apply to new calls after saving. WELCOME and END are required General intents. API URLs and credentials remain in deployment configuration.</p>
      <div class="bar save-bar"><button mat-flat-button (click)="save()" [disabled]="busy() || !dirty()">{{ busy() ? 'Saving…' : 'Save configuration' }}</button><button mat-stroked-button (click)="reload()" [disabled]="busy()">Reload configuration</button><span role="status">{{ dirty() ? 'Unsaved changes' : 'All changes saved' }}</span></div>
      <div class="layout">
        <nav aria-label="Intent configuration">
          <button mat-flat-button (click)="addIntent()" [disabled]="busy()">Add intent</button>
          @for (intent of intents(); track $index; let i = $index) {
            <button mat-button [class.selected]="selected() === i" [attr.aria-current]="selected() === i ? 'true' : null" (click)="selected.set(i)" [disabled]="busy()">{{ intentName(intent) || 'New intent' }}</button>
          }
          <button mat-stroked-button (click)="selected.set(-1)" [disabled]="busy()">Shared settings</button>
        </nav>
        <section class="editor" aria-label="Configuration editor">
          <fieldset [disabled]="busy()" [attr.inert]="busy() ? '' : null" style="border:0; padding:0; margin:0; min-width:0">
          @if (selected() === -1) {
            <h2>Shared settings</h2>
            <p class="help">Confidence thresholds range from 0 to 1. Changing the entity threshold while models are loaded requires a CLI import and API restart.</p>
            @for (entry of globalProperties(); track entry[0]) {
              <app-config-field [root]="data.json_schema" [schema]="entry[1]" [label]="title(entry[0])" [value]="draft()[entry[0]] ?? null" (changed)="setGlobal(entry[0], $event)" />
            }
          } @else if (current(); as intent) {
            <div class="bar"><h2>{{ intentName(intent) || 'New intent' }}</h2><button mat-button (click)="deleteIntent()" [disabled]="reserved(intent)">Delete intent</button></div>
            @if (reserved(intent)) { <p class="help">This required intent cannot be deleted. Keep its reserved name and General type.</p> }
            <p class="help">Names use uppercase letters, digits and underscores, starting with a letter. Rules are alternatives; all conditions within a rule must pass. Move items up to set evaluation and response order.</p>
            @for (entry of intentProperties(); track entry[0]) {
              @if (basicKeys.includes(entry[0])) {
                <app-config-field [root]="data.json_schema" [schema]="entry[1]" [label]="title(entry[0])" [value]="intent[entry[0]] ?? null" (changed)="setIntent(entry[0], $event)" />
              } @else {
                <mat-expansion-panel><mat-expansion-panel-header><mat-panel-title>{{ title(entry[0]) }}</mat-panel-title></mat-expansion-panel-header>
                <app-config-field [root]="data.json_schema" [schema]="entry[1]" [label]="title(entry[0])" [value]="intent[entry[0]] ?? null" (changed)="setIntent(entry[0], $event)" />
                </mat-expansion-panel>
              }
            }
          }
          </fieldset>
        </section>
      </div>
    }
  `,
})
export class IntentSettings {
  private readonly http = inject(HttpClient);
  private readonly dialog = inject(MatDialog);
  readonly closed = output<void>();
  readonly snapshot = signal<Snapshot | null>(null);
  readonly draft = signal<{ [key: string]: Json }>({});
  readonly selected = signal(0);
  readonly loading = signal(false);
  readonly busy = signal(false);
  readonly error = signal('');
  readonly message = signal('');
  readonly basicKeys = ['name', 'type', 'description'];
  readonly intents = computed(() => { const list = this.draft()['intents']; return Array.isArray(list) ? list : []; });
  readonly current = computed(() => { const v = this.intents()[this.selected()]; return v && typeof v === 'object' && !Array.isArray(v) ? v : null; });
  readonly dirty = computed(() => JSON.stringify(this.draft()) !== JSON.stringify(this.snapshot()?.configuration ?? {}));
  readonly globalProperties = computed(() => Object.entries(this.snapshot()?.json_schema.properties ?? {}).filter(([key]) => key !== 'intents'));
  readonly intentProperties = computed(() => Object.entries(this.snapshot()?.json_schema.$defs?.['Intent']?.properties ?? {}));
  constructor() { this.load(); }
  title(key: string): string { return key === 'api' ? 'API bindings' : key.replaceAll('_', ' ').replace(/^./, c => c.toUpperCase()); }
  intentName(value: Json): string { return value && typeof value === 'object' && !Array.isArray(value) ? String(value['name'] ?? '') : ''; }
  reserved(value: Json): boolean { return ['WELCOME', 'END'].includes(this.intentName(value)); }
  load(): void {
    this.loading.set(true); this.error.set('');
    this.http.get<Snapshot>('/api/v1/dialog-policy').subscribe({
      next: data => { this.snapshot.set(data); this.draft.set(structuredClone(data.configuration)); this.selected.set(0); this.loading.set(false); },
      error: () => { this.error.set('Could not load intent configuration. Check the service and try again.'); this.loading.set(false); },
    });
  }
  setGlobal(key: string, value: Json): void { this.draft.update(d => ({ ...d, [key]: value })); this.message.set(''); }
  setIntent(key: string, value: Json): void {
    this.setGlobal('intents', this.intents().map((v, i) => i === this.selected() ? { ...this.current(), [key]: value } : v));
  }
  addIntent(): void {
    const schema = this.snapshot()?.json_schema;
    if (!schema) return;
    this.setGlobal('intents', [...this.intents(), initial(schema.$defs?.['Intent'] ?? {}, schema)]);
    this.selected.set(this.intents().length - 1);
  }
  deleteIntent(): void {
    const intent = this.current(); if (!intent || this.reserved(intent)) return;
    const name = this.intentName(intent);
    this.confirm('Delete intent?', `Remove ${name || 'this intent'} and all its configuration? Update any next-intent references before saving.`, 'Delete intent', () => {
      this.setGlobal('intents', this.intents().filter((_, i) => i !== this.selected())); this.selected.set(0);
    });
  }
  save(): void {
    const snapshot = this.snapshot(); if (!snapshot || this.busy()) return;
    this.busy.set(true); this.error.set(''); this.message.set('');
    this.http.put<Snapshot>('/api/v1/dialog-policy', { configuration: this.draft(), revision: snapshot.revision }).subscribe({
      next: data => { this.snapshot.set(data); this.draft.set(structuredClone(data.configuration)); this.busy.set(false); this.message.set('Configuration saved. New calls will use these settings.'); },
      error: (err: HttpErrorResponse) => {
        this.busy.set(false);
        if (err.status === 409) this.error.set('Another operator changed this configuration. Your edits are kept here. Reload to get the latest version before editing again.');
        else if (err.status === 422) {
          const detail: unknown = err.error?.detail;
          this.error.set(typeof detail === 'string' ? detail : Array.isArray(detail) ? detail.map((e: { loc?: (string | number)[]; msg?: string }) => `${e.loc?.filter(v => v !== 'body').join(' → ')}: ${e.msg}`).join('\n') : 'Configuration is invalid. Review the fields and references.');
        } else this.error.set('Could not save configuration. Your edits are preserved; try again.');
      },
    });
  }
  reload(): void { if (this.dirty()) this.confirm('Discard unsaved changes?', 'Reloading replaces your edits with the latest saved configuration.', 'Discard and reload', () => this.load()); else this.load(); }
  requestClose(): void { if (this.dirty()) this.confirm('Discard unsaved changes?', 'Your intent changes have not been saved.', 'Discard changes', () => this.closed.emit()); else this.closed.emit(); }
  private confirm(title: string, message: string, action: string, confirmed: () => void): void {
    this.dialog.open(ConfirmChange, { data: { title, message, action }, width: '440px', maxWidth: '95vw' }).afterClosed().subscribe(result => { if (result === true) confirmed(); });
  }
  @HostListener('window:beforeunload', ['$event']) beforeUnload(event: BeforeUnloadEvent): void { if (this.dirty()) event.preventDefault(); }
}
