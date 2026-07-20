import { describe, expect, it } from 'vitest';
import {
  createWebChatSessionId,
  isWebChatSessionOwnedByUser,
  parseWebChatSessionUserId,
  resolveWebChatSessionId,
  webChatSessionPrefix,
} from '../chatSessionId';

describe('chatSessionId', () => {
  it('builds and parses web session ids for a user', () => {
    const sessionId = createWebChatSessionId(7);
    expect(sessionId.startsWith(webChatSessionPrefix(7))).toBe(true);
    expect(parseWebChatSessionUserId(sessionId)).toBe(7);
    expect(isWebChatSessionOwnedByUser(sessionId, 7)).toBe(true);
    expect(isWebChatSessionOwnedByUser(sessionId, 8)).toBe(false);
  });

  it('reuses a saved session id when it belongs to the current user', () => {
    const saved = 'web:3:11111111-1111-4111-8111-111111111111';
    expect(resolveWebChatSessionId(3, saved)).toBe(saved);
  });

  it('creates a new scoped session id for legacy plain uuid storage', () => {
    const resolved = resolveWebChatSessionId(3, '11111111-1111-4111-8111-111111111111');
    expect(resolved.startsWith(webChatSessionPrefix(3))).toBe(true);
    expect(resolved).not.toBe('11111111-1111-4111-8111-111111111111');
  });
});
