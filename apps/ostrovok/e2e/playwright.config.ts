import { defineConfig, devices } from '@playwright/test';
export default defineConfig({
 testDir:'.', testMatch:'trip.spec.ts', fullyParallel:false, timeout:90_000,
 use:{baseURL: process.env.E2E_BASE_URL || 'http://127.0.0.1:5173',trace:'retain-on-failure',video:'on'},
 reporter:[['list'],['html',{outputFolder:'playwright-report',open:'never'}]],
 projects:[{name:'desktop',use:{...devices['Desktop Chrome']}},{name:'mobile390',use:{...devices['Desktop Chrome'],viewport:{width:390,height:844},isMobile:true,hasTouch:true}}],
});
