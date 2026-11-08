import { TestBed } from '@angular/core/testing';
import { describe, it, expect } from 'vitest';
import { ConfigField, Schema, initial } from './config-field';

describe('Schema configuration fields', () => {
  const root: Schema = { $defs: { Field: { type: 'object', properties: { name: { type: 'string' }, normalize: { enum: ['strip', 'upper'], default: 'strip' } } } } };
  it('creates independent defaults and supports nested list editing', () => {
    const fixture = TestBed.createComponent(ConfigField);
    fixture.componentRef.setInput('schema', { type: 'array', items: { $ref: '#/$defs/Field' } });
    fixture.componentRef.setInput('root', root);
    fixture.componentRef.setInput('label', 'Fields');
    fixture.componentRef.setInput('value', []);
    let result: unknown;
    fixture.componentInstance.changed.subscribe(value => result = value);
    fixture.componentInstance.addItem();
    expect(result).toEqual([{ name: '', normalize: 'strip' }]);
    expect(initial({ $ref: '#/$defs/Field' }, root)).toEqual({ name: '', normalize: 'strip' });
  });
  it('rejects duplicate binding keys without replacing existing values', () => {
    const fixture = TestBed.createComponent(ConfigField);
    fixture.componentRef.setInput('schema', { type: 'object', additionalProperties: { type: 'string' } });
    fixture.componentRef.setInput('root', {});
    fixture.componentRef.setInput('label', 'Query');
    fixture.componentRef.setInput('value', { claim: 'claimId' });
    const input = document.createElement('input'); input.value = 'claim';
    fixture.componentInstance.addKey(input);
    expect(fixture.componentInstance.keyError).toContain('unique');
    expect(fixture.componentInstance.objectValue()).toEqual({ claim: 'claimId' });
  });
});
