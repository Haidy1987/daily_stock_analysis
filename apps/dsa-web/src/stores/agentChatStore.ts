import { create } from 'zustand';
import { agentApi } from '../api/agent';
import type { ChatSessionItem, ChatStreamRequest } from '../api/agent';
import {
  createParsedApiError,
  getParsedApiError,
  isApiRequestError,
  isParsedApiError,
  type ParsedApiError,
} from '../api/error';
import {
  CHAT_SESSION_STORAGE_KEY,
  createWebChatSessionId,
  isWebChatSessionOwnedByUser,
  resolveWebChatSessionId,
} from '../utils/chatSessionId';

export interface ProgressStep {
  type: string;
  step?: number;
  stage?: string;
  tool?: string;
  display_name?: string;
  status?: string;
  success?: boolean;
  duration?: number;
  elapsed?: number;
  timeout?: number;
  remaining?: number;
  minimum?: number;
  reason?: string;
  message?: string;
  content?: string;
  meta?: Record<string, unknown>;
}

export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  skills?: string[];
  skill?: string;
  skillNames?: string[];
  skillName?: string;
  thinkingSteps?: ProgressStep[];
}

export interface StreamMeta {
  skillNames?: string[];
  skillName?: string;
}

type StreamFailureEvent = {
  type: string;
  success?: boolean;
  content?: string;
  error?: unknown;
  message?: unknown;
  session_id?: string;
};

function getFirstMeaningfulStreamError(...candidates: Array<unknown>): unknown {
  for (const candidate of candidates) {
    if (typeof candidate === 'string') {
      if (candidate.trim() !== '') {
        return candidate;
      }
      continue;
    }

    if (candidate != null) {
      return candidate;
    }
  }

  return undefined;
}

function getStreamFailureError(
  event: StreamFailureEvent,
  fallbackMessage: string,
): ParsedApiError {
  return getParsedApiError(
    getFirstMeaningfulStreamError(
      event.error,
      event.message,
      event.content,
      fallbackMessage,
    ),
  );
}

function readStoredSessionId(): string | null {
  if (typeof localStorage === 'undefined') {
    return null;
  }
  return localStorage.getItem(CHAT_SESSION_STORAGE_KEY);
}

function persistSessionId(sessionId: string): void {
  if (typeof localStorage !== 'undefined') {
    localStorage.setItem(CHAT_SESSION_STORAGE_KEY, sessionId);
  }
}

interface AgentChatState {
  messages: Message[];
  loading: boolean;
  progressSteps: ProgressStep[];
  sessionId: string;
  ownerUserId: number | null;
  sessions: ChatSessionItem[];
  sessionsLoading: boolean;
  chatError: ParsedApiError | null;
  currentRoute: string;
  completionBadge: boolean;
  hasInitialLoad: boolean;
  abortController: AbortController | null;
}

interface AgentChatActions {
  setCurrentRoute: (path: string) => void;
  clearCompletionBadge: () => void;
  syncOwnerUserId: (userId: number) => void;
  loadSessions: () => Promise<void>;
  loadInitialSession: () => Promise<void>;
  switchSession: (targetSessionId: string) => Promise<void>;
  startNewChat: () => void;
  startStream: (payload: ChatStreamRequest, meta?: StreamMeta) => Promise<void>;
}

export const useAgentChatStore = create<AgentChatState & AgentChatActions>((set, get) => ({
  messages: [],
  loading: false,
  progressSteps: [],
  sessionId: '',
  ownerUserId: null,
  sessions: [],
  sessionsLoading: false,
  chatError: null,
  currentRoute: '',
  completionBadge: false,
  hasInitialLoad: false,
  abortController: null,

  setCurrentRoute: (path) => set({ currentRoute: path }),

  clearCompletionBadge: () => set({ completionBadge: false }),

  syncOwnerUserId: (userId) => {
    const { ownerUserId } = get();
    if (ownerUserId === userId) {
      return;
    }

    const sessionId = resolveWebChatSessionId(userId, readStoredSessionId());
    persistSessionId(sessionId);

    if (ownerUserId !== null) {
      get().abortController?.abort();
      set({
        ownerUserId: userId,
        sessionId,
        messages: [],
        sessions: [],
        hasInitialLoad: false,
        loading: false,
        progressSteps: [],
        chatError: null,
        abortController: null,
      });
      return;
    }

    set({
      ownerUserId: userId,
      sessionId,
    });
  },

  loadSessions: async () => {
    set({ sessionsLoading: true });
    try {
      const sessions = await agentApi.getChatSessions();
      set({ sessions });
    } catch {
      // Ignore load errors
    } finally {
      set({ sessionsLoading: false });
    }
  },

  loadInitialSession: async () => {
    const { hasInitialLoad, ownerUserId } = get();
    if (hasInitialLoad || ownerUserId === null) return;
    set({ hasInitialLoad: true, sessionsLoading: true });

    try {
      const sessionList = await agentApi.getChatSessions();
      set({ sessions: sessionList });

      const savedId = readStoredSessionId();
      const sessionId = resolveWebChatSessionId(ownerUserId, savedId);
      set({ sessionId });
      persistSessionId(sessionId);

      const sessionExists = sessionList.some((s) => s.session_id === sessionId);
      if (sessionExists) {
        const msgs = await agentApi.getChatSessionMessages(sessionId);
        if (msgs.length > 0) {
          set({
            messages: msgs.map((m) => ({
              id: m.id,
              role: m.role,
              content: m.content,
            })),
          });
        }
      }
    } catch {
      // Ignore
    } finally {
      set({ sessionsLoading: false });
    }
  },

  switchSession: async (targetSessionId) => {
    const { sessionId, messages, abortController, ownerUserId } = get();
    if (targetSessionId === sessionId && messages.length > 0) return;
    if (ownerUserId !== null && !isWebChatSessionOwnedByUser(targetSessionId, ownerUserId)) {
      return;
    }

    abortController?.abort();
    set({
      messages: [],
      sessionId: targetSessionId,
      loading: false,
      progressSteps: [],
      chatError: null,
      abortController: null,
    });
    persistSessionId(targetSessionId);

    try {
      const msgs = await agentApi.getChatSessionMessages(targetSessionId);
      if (get().sessionId !== targetSessionId) {
        return;
      }
      set({
        messages: msgs.map((m) => ({
          id: m.id,
          role: m.role,
          content: m.content,
        })),
      });
    } catch {
      // Ignore
    }
  },

  startNewChat: () => {
    const { ownerUserId } = get();
    if (ownerUserId === null) {
      return;
    }

    get().abortController?.abort();
    const newId = createWebChatSessionId(ownerUserId);
    set({
      sessionId: newId,
      messages: [],
      loading: false,
      progressSteps: [],
      chatError: null,
      abortController: null,
    });
    persistSessionId(newId);
  },

  startStream: async (payload, meta) => {
    if (get().loading) return;
    const { abortController: prevAc, sessionId: storeSessionId, ownerUserId } = get();
    if (ownerUserId === null) {
      set({
        chatError: createParsedApiError({
          title: '会话未就绪',
          message: '用户信息尚未加载完成，请稍后重试。',
          rawMessage: 'Agent chat owner user id is not available yet.',
          category: 'unknown',
        }),
      });
      return;
    }

    prevAc?.abort();

    const ac = new AbortController();
    set({ abortController: ac });

    const requestedSessionId = payload.session_id || storeSessionId;
    const streamSessionId = isWebChatSessionOwnedByUser(requestedSessionId, ownerUserId)
      ? requestedSessionId
      : createWebChatSessionId(ownerUserId);
    if (streamSessionId !== storeSessionId) {
      set({ sessionId: streamSessionId });
      persistSessionId(streamSessionId);
    }

    const streamPayload: ChatStreamRequest = {
      ...payload,
      session_id: streamSessionId,
    };

    const skillNames = meta?.skillNames?.length
      ? meta.skillNames
      : [meta?.skillName ?? '通用'];
    const skillName = skillNames.join('、');

    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: payload.message,
      skills: payload.skills,
      skill: payload.skills?.[0],
      skillNames,
      skillName,
    };

    set((s) => ({
      messages: [...s.messages, userMessage],
      loading: true,
      progressSteps: [],
      chatError: null,
      sessions: s.sessions.some((x) => x.session_id === streamSessionId)
        ? s.sessions
        : [
            {
              session_id: streamSessionId,
              title: payload.message.slice(0, 60),
              message_count: 1,
              created_at: new Date().toISOString(),
              last_active: new Date().toISOString(),
            },
            ...s.sessions,
          ],
    }));

    try {
      const response = await agentApi.chatStream(streamPayload, { signal: ac.signal });
      const reader = response.body!.getReader();
      const decoder = new TextDecoder();
      let buf = '';
      let finalContent: string | null = null;
      let receivedDoneEvent = false;
      const currentProgressSteps: ProgressStep[] = [];
      const processLine = (line: string) => {
        if (!line.startsWith('data: ')) return;

        const event = JSON.parse(line.slice(6)) as ProgressStep;
        if (event.type === 'done') {
          receivedDoneEvent = true;
          const doneEvent = event as unknown as StreamFailureEvent;
          if (doneEvent.success === false) {
            throw getStreamFailureError(doneEvent, '大模型调用出错，请检查 API Key 配置');
          }
          finalContent = doneEvent.content ?? '';
          if (
            typeof doneEvent.session_id === 'string'
            && isWebChatSessionOwnedByUser(doneEvent.session_id, ownerUserId)
          ) {
            set({ sessionId: doneEvent.session_id });
            persistSessionId(doneEvent.session_id);
          }
          return;
        }

        if (event.type === 'error') {
          throw getStreamFailureError(event as unknown as StreamFailureEvent, '分析出错');
        }

        currentProgressSteps.push(event);
        set((s) => ({ progressSteps: [...s.progressSteps, event] }));
      };

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        const lines = buf.split('\n');
        buf = lines.pop() ?? '';

        for (const line of lines) {
          try {
            processLine(line);
          } catch (parseErr: unknown) {
            if (isParsedApiError(parseErr) || isApiRequestError(parseErr)) {
              throw parseErr;
            }
          }
        }
      }

      if (buf.trim().startsWith('data: ')) {
        try {
          processLine(buf.trim());
        } catch (parseErr: unknown) {
          if (isParsedApiError(parseErr) || isApiRequestError(parseErr)) {
            throw parseErr;
          }
        }
      }

      if (!receivedDoneEvent && !ac.signal.aborted) {
        throw createParsedApiError({
          title: '回复未完整返回',
          message: 'Agent 流式响应在完成前中断，请重试。',
          rawMessage: 'Agent stream ended before a done event was received.',
          category: 'upstream_network',
        });
      }

      const { sessionId: currentSessionId, currentRoute } = get();
      const shouldAppend =
        currentSessionId === streamSessionId && !ac.signal.aborted;

      if (shouldAppend) {
        set((s) => ({
          messages: [
            ...s.messages,
            {
              id: (Date.now() + 1).toString(),
              role: 'assistant',
              content: finalContent || '（无内容）',
              skills: payload.skills,
              skill: payload.skills?.[0],
              skillNames,
              skillName,
              thinkingSteps: [...currentProgressSteps],
            },
          ],
        }));
      }

      if (currentRoute !== '/chat') {
        set({ completionBadge: true });
      }
    } catch (error: unknown) {
      if (error instanceof Error && error.name === 'AbortError') {
        // User-initiated abort: silent, no badge
      } else {
        set({ chatError: getParsedApiError(error) });
        const { currentRoute } = get();
        if (currentRoute !== '/chat') {
          set({ completionBadge: true });
        }
      }
    } finally {
      const { abortController: currentAc } = get();
      if (currentAc === ac) {
        set({
          loading: false,
          progressSteps: [],
          abortController: null,
        });
      }
      await get().loadSessions();
    }
  },
}));
