import '@testing-library/jest-dom/vitest';
import { afterEach, vi } from 'vitest';
import { cleanup } from '@testing-library/react';

// jsdom lacks the Web Crypto digest used by the audit payload hash — stub it
// deterministically so EvidenceInspector tests don't depend on browser crypto.
if (!globalThis.crypto?.subtle) {
  globalThis.crypto = {
    ...globalThis.crypto,
    subtle: {
      digest: vi.fn().mockResolvedValue(new ArrayBuffer(32)),
    },
  };
}

afterEach(() => {
  cleanup();
});
