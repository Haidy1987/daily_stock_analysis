import { generateUUID } from './uuid';

export const CHAT_SESSION_STORAGE_KEY = 'dsa_chat_session_id';

export function webChatSessionPrefix(userId: number): string {
  return `web:${userId}:`;
}

export function createWebChatSessionId(userId: number): string {
  return `${webChatSessionPrefix(userId)}${generateUUID()}`;
}

export function parseWebChatSessionUserId(sessionId: string): number | null {
  const match = /^web:(\d+):/.exec(sessionId);
  if (!match) {
    return null;
  }
  const userId = Number(match[1]);
  return Number.isFinite(userId) ? userId : null;
}

export function isWebChatSessionOwnedByUser(sessionId: string, userId: number): boolean {
  return sessionId.startsWith(webChatSessionPrefix(userId));
}

export function resolveWebChatSessionId(
  userId: number,
  savedSessionId: string | null | undefined,
): string {
  if (savedSessionId && isWebChatSessionOwnedByUser(savedSessionId, userId)) {
    return savedSessionId;
  }
  return createWebChatSessionId(userId);
}
