import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting, HttpTestingController } from '@angular/common/http/testing';
import { describe, it, expect } from 'vitest';
import { IntentSettings } from './intent-settings';

describe('Intent settings persistence', () => {
  it('preserves edits on conflict and sends the revision read from the server', () => {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
    const fixture = TestBed.createComponent(IntentSettings);
    const http = TestBed.inject(HttpTestingController);
    http.expectOne('/api/v1/dialog-policy').flush({ configuration: { intents: [] }, revision: 'original', json_schema: {} });
    const component = fixture.componentInstance;
    component.setGlobal('clarification_template', 'Please clarify.');
    component.save();
    const request = http.expectOne('/api/v1/dialog-policy');
    expect(request.request.method).toBe('PUT');
    expect(request.request.body.revision).toBe('original');
    request.flush({}, { status: 409, statusText: 'Conflict' });
    expect(component.draft()['clarification_template']).toBe('Please clarify.');
    expect(component.dirty()).toBe(true);
    expect(component.error()).toContain('Another operator');
    expect(component.busy()).toBe(false);
    http.verify();
  });
});
