// Fixed task payloads used by both unit tests and Playwright E2E

export interface Task {
  id: string
  task_key: string
  category: string
  task_number: number
  title: string
  completed: boolean
  scheduled_date: string | null
  recurrence_rule: string | null
  created_at: string
  is_template: boolean
  parent_task_id: string | null
  duration_minutes: number | null
  priority: number | null
  projected?: boolean
}

export const TODAY = '2026-05-03'
export const TOMORROW = '2026-05-04'

export const TASK_A: Task = {
  id: 'task-001',
  task_key: 'T-01',
  category: 'T',
  task_number: 1,
  title: 'Buy groceries',
  completed: false,
  scheduled_date: `${TODAY}T10:00`,
  recurrence_rule: null,
  created_at: `${TODAY}T08:00:00`,
  is_template: false,
  parent_task_id: null,
  duration_minutes: 30,
  priority: 2,
}

export const TASK_B: Task = {
  id: 'task-002',
  task_key: 'T-02',
  category: 'T',
  task_number: 2,
  title: 'Read a book',
  completed: false,
  scheduled_date: `${TODAY}T14:00`,
  recurrence_rule: null,
  created_at: `${TODAY}T08:05:00`,
  is_template: false,
  parent_task_id: null,
  duration_minutes: 60,
  priority: 1,
}

export const TASK_DONE: Task = {
  id: 'task-003',
  task_key: 'T-03',
  category: 'T',
  task_number: 3,
  title: 'Morning run',
  completed: true,
  scheduled_date: `${TODAY}T07:00`,
  recurrence_rule: null,
  created_at: `${TODAY}T07:00:00`,
  is_template: false,
  parent_task_id: null,
  duration_minutes: 30,
  priority: 2,
}

export const TASK_BACKLOG: Task = {
  id: 'task-004',
  task_key: 'T-04',
  category: 'T',
  task_number: 4,
  title: 'Plan vacation',
  completed: false,
  scheduled_date: null,
  recurrence_rule: null,
  created_at: `${TODAY}T09:00:00`,
  is_template: false,
  parent_task_id: null,
  duration_minutes: null,
  priority: 0,
}

export const TASK_MEETING: Task = {
  id: 'task-005',
  task_key: 'M-01',
  category: 'M',
  task_number: 1,
  title: 'Team sync',
  completed: false,
  scheduled_date: `${TODAY}T11:00`,
  recurrence_rule: null,
  created_at: `${TODAY}T08:10:00`,
  is_template: false,
  parent_task_id: null,
  duration_minutes: 60,
  priority: 3,
}

export const TASK_OVERDUE: Task = {
  id: 'task-006',
  task_key: 'T-06',
  category: 'T',
  task_number: 6,
  title: 'Submit report',
  completed: false,
  scheduled_date: '2026-05-01T09:00',
  recurrence_rule: null,
  created_at: '2026-04-30T08:00:00',
  is_template: false,
  parent_task_id: null,
  duration_minutes: 45,
  priority: 3,
}

// Payload for /tasks/for-date (today)
export const FOR_DATE_TASKS = [TASK_A, TASK_B, TASK_DONE, TASK_MEETING]

// Payload for /tasks (all tasks)
export const ALL_TASKS = [TASK_A, TASK_B, TASK_DONE, TASK_BACKLOG, TASK_MEETING, TASK_OVERDUE]

// Payload for /tasks/overdue
export const OVERDUE_TASKS = [TASK_OVERDUE]

// Payload for /conversations?limit=3
export const CONVERSATIONS_RECENT = [
  { id: 1, title: 'Morning brief' },
  { id: 2, title: 'Weekly review' },
  { id: 3, title: 'Gym scheduling' },
]

// Payload for /conversations/:id
export const CONVERSATION_1 = {
  id: 1,
  messages: [
    { role: 'user', content: 'Hello' },
    { role: 'assistant', content: 'Hi there!' },
  ],
}

// Payload for /conversation/new
export const NEW_CONVERSATION = { id: 42 }

// Payload for /chat (happy path)
export const CHAT_RESPONSE = {
  response: 'Sure, I can help with that.',
  tasks: ALL_TASKS,
  title: 'Morning brief',
}

// Payload for /settings
export const SETTINGS = {
  default_category: 'T',
  default_priority: 'medium',
  conflict_resolution: 'overlap',
}
