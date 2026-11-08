import { bootstrapApplication } from '@angular/platform-browser';
import { AppComponent } from './app/app';
import { provideHttpClient } from '@angular/common/http';

bootstrapApplication(AppComponent, { providers: [provideHttpClient()] }).catch(console.error);
