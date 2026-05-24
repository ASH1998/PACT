import { describe, it, expect } from 'vitest';

describe('PACT Frontend', () => {
  it('imports api client types', async () => {
    const mod = await import('../api/client');
    expect(mod.getRuns).toBeDefined();
    expect(mod.getReplay).toBeDefined();
    expect(mod.runScenario).toBeDefined();
  });
});
