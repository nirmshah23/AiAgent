import { ChangeDetectionStrategy, Component, computed, input, output } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';

export type Json = string | number | boolean | null | Json[] | { [key: string]: Json };
export interface Schema {
  $ref?: string; $defs?: Record<string, Schema>; anyOf?: Schema[];
  type?: string; title?: string; description?: string; enum?: string[];
  properties?: Record<string, Schema>; additionalProperties?: Schema;
  items?: Schema; default?: Json; minimum?: number; maximum?: number;
  exclusiveMinimum?: number; minLength?: number; maxLength?: number; pattern?: string;
}

export function resolve(schema: Schema, root: Schema, value: Json = null): Schema {
  if (schema.$ref) return resolve(root.$defs?.[schema.$ref.split('/').pop() ?? ''] ?? {}, root, value);
  if (schema.anyOf) {
    const choices = schema.anyOf.filter(s => s.type !== 'null');
    return resolve(choices.find(s => s.type === (Array.isArray(value) ? 'array' : 'string')) ?? choices[0], root, value);
  }
  return schema;
}

export function initial(schema: Schema, root: Schema): Json {
  if (schema.default !== undefined) return structuredClone(schema.default);
  const s = resolve(schema, root);
  if (s.type === 'object') return Object.fromEntries(Object.entries(s.properties ?? {}).map(([k, v]) => [k, initial(v, root)]));
  if (s.type === 'array') return [];
  if (s.type === 'number' || s.type === 'integer') return s.minimum ?? 0;
  return s.enum?.[0] ?? '';
}

@Component({
  selector: 'app-config-field', standalone: true,
  imports: [FormsModule, MatButtonModule, MatFormFieldModule, MatInputModule, MatSelectModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  styles: [`
    :host { display: block; min-width: 0; }
    mat-form-field { width: 100%; }
    fieldset { min-width: 0; margin: 12px 0 20px; padding: 16px; border: 1px solid var(--mat-sys-outline-variant); border-radius: 12px; }
    legend { padding: 0 8px; font-weight: 600; }
    .item { border-left: 3px solid var(--mat-sys-outline-variant); padding: 8px 0 8px 14px; margin-bottom: 12px; }
    .row { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
    .row app-config-field { flex: 1; min-width: 140px; }
    .row mat-form-field { flex: 1; min-width: 120px; }
    .muted { color: var(--mat-sys-on-surface-variant); font-size: 13px; }
    textarea { min-height: 72px; }
  `],
  template: `
    @if (nullable() && value() === null) {
      <div class="row"><p>{{ label() }}: not configured</p><button mat-stroked-button type="button" (click)="changed.emit(initialValue())">Configure {{ label() }}</button></div>
    } @else {
      @if (nullable()) { <button mat-button type="button" (click)="changed.emit(null)">Clear {{ label() }}</button> }
      @if (union()) {
        <mat-form-field><mat-label>{{ label() }} format</mat-label><mat-select [ngModel]="isArray() ? 'list' : 'text'" (ngModelChange)="changed.emit($event === 'list' ? [] : '')"><mat-option value="text">Text</mat-option><mat-option value="list">List of values</mat-option></mat-select></mat-form-field>
      }
      @switch (resolved().type) {
        @case ('object') {
          <fieldset><legend>{{ label() }}</legend>
          @if (resolved().properties) {
            @for (entry of properties(); track entry[0]) {
              <app-config-field [schema]="entry[1]" [root]="root()" [label]="title(entry[0])" [value]="objectValue()[entry[0]] ?? null" (changed)="set(entry[0], $event)" />
            }
          } @else {
            @for (entry of bindings(); track entry[0]) {
              <div class="row"><strong>{{ entry[0] }}</strong><app-config-field [schema]="resolved().additionalProperties ?? {}" [root]="root()" [label]="entry[0] + ' binding'" [value]="entry[1]" (changed)="set(entry[0], $event)" /><button mat-button type="button" (click)="removeKey(entry[0])">Remove {{ entry[0] }}</button></div>
            }
            <div class="row"><mat-form-field><mat-label>New {{ label() }} key</mat-label><input matInput #keyInput (input)="keyError = ''"></mat-form-field><button mat-stroked-button type="button" (click)="addKey(keyInput)">Add binding</button></div>
            @if (keyError) { <p role="alert">{{ keyError }}</p> }
          }
          </fieldset>
        }
        @case ('array') {
          <fieldset><legend>{{ label() }}</legend>
          @if (!arrayValue().length) { <p class="muted">No {{ label().toLowerCase() }} configured.</p> }
          @for (item of arrayValue(); track $index; let i = $index) {
            <div class="item"><app-config-field [schema]="resolved().items ?? {}" [root]="root()" [label]="label() + ' ' + (i + 1)" [value]="item" (changed)="setItem(i, $event)" />
            <button mat-button type="button" (click)="removeItem(i)">Remove {{ label() }} {{ i + 1 }}</button>
            @if (i > 0) { <button mat-button type="button" (click)="moveUp(i)">Move up</button> }</div>
          }
          <button mat-stroked-button type="button" (click)="addItem()">Add {{ label() }}</button></fieldset>
        }
        @default {
          <mat-form-field appearance="outline"><mat-label>{{ label() }}</mat-label>
          @if (resolved().enum) {
            <mat-select [ngModel]="value()" (ngModelChange)="changed.emit($event)">@for (choice of resolved().enum; track choice) { <mat-option [value]="choice">{{ choice }}</mat-option> }</mat-select>
          } @else if (resolved().type === 'number' || resolved().type === 'integer') {
            <input matInput type="number" [ngModel]="value()" [min]="resolved().minimum ?? resolved().exclusiveMinimum ?? null" [max]="resolved().maximum ?? null" [step]="resolved().type === 'integer' ? 1 : 0.01" (ngModelChange)="changed.emit($event)">
          } @else if (multiline()) {
            <textarea matInput [ngModel]="value()" [attr.maxlength]="resolved().maxLength ?? null" (ngModelChange)="changed.emit($event)"></textarea>
          } @else {
            <input matInput [ngModel]="value()" [attr.maxlength]="resolved().maxLength ?? null" (ngModelChange)="changed.emit($event)">
          }
          </mat-form-field>
        }
      }
    }
  `,
})
export class ConfigField {
  readonly schema = input.required<Schema>();
  readonly root = input.required<Schema>();
  readonly label = input.required<string>();
  readonly value = input.required<Json>();
  readonly changed = output<Json>();
  readonly resolved = computed(() => resolve(this.schema(), this.root(), this.value()));
  readonly nullable = computed(() => this.schema().anyOf?.some(s => s.type === 'null') ?? false);
  readonly union = computed(() => (this.schema().anyOf?.filter(s => s.type !== 'null').length ?? 0) > 1);
  readonly isArray = computed(() => Array.isArray(this.value()));
  readonly multiline = computed(() => /description|template|responses/i.test(this.label()));
  readonly objectValue = computed(() => { const v = this.value(); return v && typeof v === 'object' && !Array.isArray(v) ? v : {}; });
  readonly arrayValue = computed(() => { const v = this.value(); return Array.isArray(v) ? v : []; });
  readonly properties = computed(() => Object.entries(this.resolved().properties ?? {}));
  readonly bindings = computed(() => Object.entries(this.objectValue()));
  keyError = '';
  title(key: string): string { return key.replaceAll('_', ' ').replace(/^./, c => c.toUpperCase()); }
  initialValue(): Json { return initial(resolve(this.schema(), this.root()), this.root()); }
  set(key: string, value: Json): void { this.changed.emit({ ...this.objectValue(), [key]: value }); }
  removeKey(key: string): void { const v = { ...this.objectValue() }; delete v[key]; this.changed.emit(v); }
  addKey(input: HTMLInputElement): void {
    const key = input.value.trim();
    if (!key || Object.hasOwn(this.objectValue(), key)) { this.keyError = 'Enter a unique, nonempty key.'; return; }
    this.set(key, initial(this.resolved().additionalProperties ?? {}, this.root())); input.value = '';
  }
  setItem(index: number, value: Json): void { this.changed.emit(this.arrayValue().map((v, i) => i === index ? value : v)); }
  addItem(): void { this.changed.emit([...this.arrayValue(), initial(this.resolved().items ?? {}, this.root())]); }
  removeItem(index: number): void { this.changed.emit(this.arrayValue().filter((_, i) => i !== index)); }
  moveUp(index: number): void { const list = [...this.arrayValue()]; [list[index - 1], list[index]] = [list[index], list[index - 1]]; this.changed.emit(list); }
}
