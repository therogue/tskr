// Minimal fetch mock keyed by URL pattern.
// Install by calling setupFetchMock() in beforeEach/setup.

import {
  FOR_DATE_TASKS,
  ALL_TASKS,
  OVERDUE_TASKS,
  CONVERSATIONS_RECENT,
  CONVERSATION_1,
  NEW_CONVERSATION,
  CHAT_RESPONSE,
  SETTINGS,
} from '../fixtures/tasks'

type Handler = (url: string, init?: RequestInit) => Response

const DEFAULT_HANDLERS: Array<{ match: (url: string) => boolean; handler: Handler }> = [
  {
    match: (u) => u.includes('/tasks/for-date'),
    handler: () => jsonResponse(FOR_DATE_TASKS),
  },
  {
    match: (u) => u.includes('/tasks/overdue'),
    handler: () => jsonResponse(OVERDUE_TASKS),
  },
  {
    match: (u) => u.includes('/tasks/') && u.includes('PATCH'),
    handler: (_u, _i) => jsonResponse({}),
  },
  {
    match: (u) => /\/tasks\/[^/]+$/.test(u) && !u.includes('for-date') && !u.includes('overdue'),
    handler: (_u, init) => {
      if (init?.method === 'DELETE') return jsonResponse({ status: 'deleted' })
      if (init?.method === 'PATCH') return jsonResponse(ALL_TASKS[0])
      return jsonResponse(ALL_TASKS)
    },
  },
  {
    match: (u) => u.endsWith('/tasks'),
    handler: () => jsonResponse(ALL_TASKS),
  },
  {
    match: (u) => u.includes('/conversation/new'),
    handler: () => jsonResponse(NEW_CONVERSATION),
  },
  {
    match: (u) => u.includes('/conversations') && /\/conversations\/\d+/.test(u),
    handler: () => jsonResponse(CONVERSATION_1),
  },
  {
    match: (u) => u.includes('/conversations'),
    handler: () => jsonResponse(CONVERSATIONS_RECENT),
  },
  {
    match: (u) => u.endsWith('/chat'),
    handler: () => jsonResponse(CHAT_RESPONSE),
  },
  {
    match: (u) => u.includes('/settings'),
    handler: (_u, init) => {
      if (init?.method === 'PATCH') return jsonResponse(SETTINGS)
      return jsonResponse(SETTINGS)
    },
  },
]

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

export function setupFetchMock(overrides?: Array<{ match: (url: string) => boolean; handler: Handler }>) {
  const handlers = [...(overrides ?? []), ...DEFAULT_HANDLERS]

  const mockFetch = vi.fn((url: string, init?: RequestInit) => {
    for (const h of handlers) {
      if (h.match(url)) return Promise.resolve(h.handler(url, init))
    }
    console.warn('[fetchMock] unhandled:', url)
    return Promise.resolve(jsonResponse({}, 404))
  })

  vi.stubGlobal('fetch', mockFetch)
  return mockFetch
}

export function getFetchMock(): ReturnType<typeof vi.fn> {
  return (globalThis as unknown as { fetch: ReturnType<typeof vi.fn> }).fetch
}
