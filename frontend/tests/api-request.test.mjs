import assert from 'node:assert/strict';
import test from 'node:test';
import { requestJson, resolveApiBase } from '../src/api/request.mjs';

test('production API base never falls back to localhost', () => {
  assert.equal(resolveApiBase('', false), null);
  assert.equal(resolveApiBase('https://api.example.test/', false), 'https://api.example.test');
  assert.equal(resolveApiBase('http://api.example.test', false), null);
});

test('development API base falls back to local backend', () => {
  assert.equal(resolveApiBase('', true), 'http://localhost:8000');
});

test('request timeout returns a clear timeout error', async () => {
  const fetchImpl = (_url, { signal }) => new Promise((_resolve, reject) => {
    signal.addEventListener('abort', () => reject(new DOMException('aborted', 'AbortError')), { once: true });
  });
  await assert.rejects(
    requestJson('/slow', { baseUrl: 'https://api.example.test', timeoutMs: 5, fetchImpl }),
    /timed out after 5ms/,
  );
});

test('connection failures return a clear connection error', async () => {
  await assert.rejects(
    requestJson('/health', {
      baseUrl: 'https://api.example.test',
      fetchImpl: async () => { throw new TypeError('fetch failed'); },
    }),
    /Unable to connect to API/,
  );
});
