import { TextDecoder, TextEncoder } from 'util';

import '@testing-library/jest-dom';

// jsdom lacks TextEncoder/TextDecoder globals that react-router v7 (and
// some other modern libs) expect. Polyfill from Node's util.
if (typeof globalThis.TextEncoder === 'undefined') {
  globalThis.TextEncoder = TextEncoder as typeof globalThis.TextEncoder;
}
if (typeof globalThis.TextDecoder === 'undefined') {
  globalThis.TextDecoder = TextDecoder as typeof globalThis.TextDecoder;
}
