import { test, expect } from '@playwright/test'
import type { Page, Route } from '@playwright/test'

// ── Fixtures ─────────────────────────────────────────────────────────────────

const TODAY = new Date().toISOString().slice(0, 10)
const TOMORROW = new Date(Date.now() + 86400000).toISOString().slice(0, 10)

const TASKS = [
  {
    id: 'task-001', task_key: 'T-01', category: 'T', task_number: 1,
    title: 'Buy groceries', completed: false,
    scheduled_date: `${TODAY}T10:00`, recurrence_rule: null,
    created_at: `${TODAY}T08:00:00`, is_template: false,
    parent_task_id: null, duration_minutes: 30, priority: 2,
  },
  {
    id: 'task-002', task_key: 'T-02', category: 'T', task_number: 2,
    title: 'Read a book', completed: false,
    scheduled_date: `${TODAY}T14:00`, recurrence_rule: null,
    created_at: `${TODAY}T08:05:00`, is_template: false,
    parent_task_id: null, duration_minutes: 60, priority: 1,
  },
  {
    id: 'task-003', task_key: 'T-03', category: 'T', task_number: 3,
    title: 'Plan vacation', completed: false,
    scheduled_date: null, recurrence_rule: null,
    created_at: `${TODAY}T09:00:00`, is_template: false,
    parent_task_id: null, duration_minutes: null, priority: 0,
  },
]

const SETTINGS = { default_category: 'T', default_priority: 'medium', conflict_resolution: 'overlap' }
const NEW_CONV = { id: 42 }
const CHAT_RESP = { response: 'Sure, I can help with that.', tasks: TASKS, title: null }

// ── Mock backend ──────────────────────────────────────────────────────────────

async function mockBackend(page: Page) {
  const patched: Record<string, unknown> = {}

  await page.route('**/tasks/for-date**', (route: Route) =>
    route.fulfill({ json: TASKS.filter(t => t.scheduled_date?.startsWith(TODAY)) })
  )
  await page.route('**/tasks/overdue**', (route: Route) => route.fulfill({ json: [] }))
  await page.route('**/tasks', async (route: Route) => {
    if (route.request().method() === 'GET') {
      return route.fulfill({ json: TASKS })
    }
    return route.continue()
  })
  await page.route('**/tasks/**', async (route: Route) => {
    const method = route.request().method()
    // Let more specific GET routes (for-date, overdue) handle their requests.
    // Without this, the catch-all swallows them and (with route.continue) hits
    // the real backend on localhost:8000.
    if (method !== 'PATCH' && method !== 'DELETE') {
      return route.fallback()
    }
    const url = route.request().url()
    const id = url.split('/tasks/')[1]
    if (method === 'PATCH') {
      const body = JSON.parse(route.request().postData() ?? '{}')
      patched[id] = body
      const task = TASKS.find(t => t.id === id) ?? TASKS[0]
      return route.fulfill({ json: { ...task, ...body } })
    }
    return route.fulfill({ json: { status: 'deleted' } })
  })
  await page.route('**/conversation/new', (route: Route) =>
    route.fulfill({ json: NEW_CONV })
  )
  await page.route('**/conversations/**', (route: Route) =>
    route.fulfill({ json: { id: 1, messages: [] } })
  )
  await page.route('**/conversations**', (route: Route) =>
    route.fulfill({ json: [{ id: 1, title: 'Old chat' }] })
  )
  await page.route('**/chat', (route: Route) =>
    route.fulfill({ json: CHAT_RESP })
  )
  await page.route('**/settings', async (route: Route) => {
    if (route.request().method() === 'PATCH') {
      return route.fulfill({ json: SETTINGS })
    }
    return route.fulfill({ json: SETTINGS })
  })

  return patched
}

// ── Tests ─────────────────────────────────────────────────────────────────────

test.describe('E2E smoke', () => {
  test.beforeEach(async ({ page }) => {
    await mockBackend(page)
    await page.goto('/')
    // Wait for tasks to render
    await page.waitForSelector('.task-item', { timeout: 10000 })
  })

  test('1. App loads with Day view and seeded tasks', async ({ page }) => {
    await expect(page.getByText('Buy groceries')).toBeVisible()
    await expect(page.getByText('Read a book')).toBeVisible()
    await expect(page.getByRole('button', { name: /day view/i })).toBeVisible()
  })

  test('2. Tab navigation: Backlog → Completed → Day', async ({ page }) => {
    await page.getByRole('button', { name: /backlog/i }).click()
    await expect(page.getByRole('button', { name: /backlog/i })).toHaveClass(/active/)

    await page.getByRole('button', { name: /completed/i }).click()
    await expect(page.getByRole('button', { name: /completed/i })).toHaveClass(/active/)

    await page.getByRole('button', { name: /day view/i }).click()
    await expect(page.getByRole('button', { name: /day view/i })).toHaveClass(/active/)
  })

  test('3. Select one task → trash → confirm → task removed', async ({ page }) => {
    // Track DELETE calls — register BEFORE the click that triggers the request.
    const deleteCalls: string[] = []
    page.on('request', req => { if (req.method() === 'DELETE') deleteCalls.push(req.url()) })

    // Click trash icon on first task (uses aria-label "Delete task", not text "Delete")
    await page.locator('.task-delete-btn').first().click()
    // Confirm popup appears
    const popup = page.locator('.confirm-popup')
    await expect(popup).toBeVisible()
    await expect(popup.getByText(/are you sure/i)).toBeVisible()
    // Confirm popup uses Cancel / Delete buttons; scope to popup to avoid the
    // task-row trash button (which is named "Delete task").
    await popup.getByRole('button', { name: /^delete$/i }).click()
    // Popup closes and a DELETE was issued
    await expect(popup).toBeHidden()
    expect(deleteCalls.length).toBeGreaterThan(0)
  })

  test('4. Open chat → send a message → response bubble appears', async ({ page }) => {
    const input = page.locator('.chat-input')
    await input.fill('hi')
    await page.locator('.chat-send-btn').click()
    await expect(page.getByText('Sure, I can help with that.')).toBeVisible()
  })

  test('5. Open Settings → change conflict resolution → save', async ({ page }) => {
    await page.getByRole('button', { name: /settings/i }).click()
    await expect(page.getByText(/allow overlap/i)).toBeVisible()
    // Click a different radio
    await page.getByText(/move to backlog/i).click()
    await page.getByRole('button', { name: /save/i }).click()
    // Modal closes
    await expect(page.getByText(/allow overlap/i)).not.toBeVisible({ timeout: 3000 })
  })

  test('6. Ctrl+. opens QuickEntry, Esc closes it', async ({ page }) => {
    await page.keyboard.press('Control+.')
    await expect(page.locator('.quick-entry-input')).toBeVisible()
    await page.keyboard.press('Escape')
    await expect(page.locator('.quick-entry-input')).not.toBeVisible({ timeout: 3000 })
  })
})
