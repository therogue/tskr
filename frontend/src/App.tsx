import { useState, useEffect } from 'react'
import TaskList from './components/TaskList'
import ChatInterface from './components/ChatInterface'
import SettingsModal from './components/SettingsModal'
import QuickEntry from './components/QuickEntry'
import { useFeatureFlag } from './featureFlags'
import { useTheme } from './hooks/useTheme'
import Icon from './components/Icon'
import WidgetPanel from './components/WidgetPanel'

// Assumption: Task matches backend Task model, with optional projected field
interface Task {
  id: string;
  task_key: string;
  category: string;
  task_number: number;
  title: string;
  completed: boolean;
  scheduled_date: string | null; // YYYY-MM-DD or YYYY-MM-DDTHH:MM
  recurrence_rule: string | null;
  created_at: string;
  is_template: boolean;
  parent_task_id: string | null;
  duration_minutes: number | null;
  priority: number | null; // 0=None, 1=Low, 2=Medium, 3=High, 4=Critical
  projected?: boolean;
}

type ViewMode = "day" | "all" | "completed" | "backlog";

const API_URL = "http://localhost:8000";

// Helper to format Date to YYYY-MM-DD
function formatDateStr(date: Date): string {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}

function App() {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [overdueTasks, setOverdueTasks] = useState<Task[]>([]);
  const [viewMode, setViewMode] = useState<ViewMode>('day');
  const [showSettings, setShowSettings] = useState(false);
  const [quickEntryOpen, setQuickEntryOpen] = useState(false);

  const themeToggleEnabled = useFeatureFlag('ux_v2.theme_toggle')
  const [theme, toggleTheme] = useTheme()

  const CHAT_COLLAPSED_KEY = 'chatCollapsed'
  const [chatCollapsed, setChatCollapsed] = useState<boolean>(() => {
    return localStorage.getItem(CHAT_COLLAPSED_KEY) === 'true'
  })
  const [chatOpen, setChatOpen] = useState(false)

  function handleToggleChat() {
    setChatCollapsed(prev => {
      const next = !prev
      localStorage.setItem(CHAT_COLLAPSED_KEY, String(next))
      return next
    })
  }

  // Get today's date in YYYY-MM-DD format
  const todayStr = formatDateStr(new Date());
  const [selectedDate, setSelectedDate] = useState<string>(todayStr);

  // Ctrl+. / Cmd+. opens quick entry
  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "." && (e.ctrlKey || e.metaKey)) {
        e.preventDefault();
        setQuickEntryOpen((prev) => !prev);
      }
    }
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, []);

  useEffect(() => {
    fetchTasks();
  }, [viewMode, selectedDate]);

  async function fetchTasks() {
    try {
      // Day view uses date-specific endpoint, others use /tasks
      const url =
        viewMode === "day"
          ? `${API_URL}/tasks/for-date?date=${selectedDate}`
          : `${API_URL}/tasks`;
      // Overdue is a separate query, only relevant when viewing today's day view.
      const showOverdue = viewMode === "day" && selectedDate === todayStr;
      const [res, overdueRes] = await Promise.all([
        fetch(url),
        showOverdue ? fetch(`${API_URL}/tasks/overdue`) : Promise.resolve(null),
      ]);
      const data = await res.json();
      setTasks(data);
      if (overdueRes) {
        const overdueData = await overdueRes.json();
        setOverdueTasks(overdueData);
      } else {
        setOverdueTasks([]);
      }
    } catch (err) {
      console.error("Failed to fetch tasks:", err);
    }
  }

  function handleTasksUpdate() {
    // Refetch tasks after any update
    fetchTasks();
  }

  const uxV2 = useFeatureFlag('ux_v2')
  const headerActions = (
    <>
      {themeToggleEnabled && (
        <button
          className="header-theme-btn"
          onClick={toggleTheme}
          aria-label={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
          title={theme === 'dark' ? 'Light mode' : 'Dark mode'}
        >
          <Icon n={theme === 'dark' ? 'sun' : 'moon'} size={20} />
        </button>
      )}
      <button className="header-settings-btn" onClick={() => setShowSettings(true)} aria-label="Settings">
        <Icon n="settings" size={20} />
      </button>
    </>
  )

  return (
    <div className={`app${uxV2 ? ' ux-v2' : ''}`}>
      <header className="header">
        <h1><img src="/hakadorio-logo.png" alt="hakadorio" className="header-logo" />Hakadorio</h1>
        <div className="header-actions">{headerActions}</div>
      </header>
      {showSettings && (
        <SettingsModal
          onClose={() => setShowSettings(false)}
          taskCategories={[...new Set(tasks.map(t => t.category))]}
        />
      )}
      {uxV2 ? (
        <main className="main main--v2">
          <TaskList
            tasks={tasks}
            overdueTasks={overdueTasks}
            viewMode={viewMode}
            selectedDate={selectedDate}
            todayStr={todayStr}
            onViewModeChange={setViewMode}
            onDateChange={setSelectedDate}
            onTasksUpdate={handleTasksUpdate}
          />
          <div className="right-panel">
            <WidgetPanel
              tasks={tasks}
              selectedDate={selectedDate}
              onOpenChat={() => setChatOpen(true)}
            />
            <ChatInterface
              onTasksUpdate={handleTasksUpdate}
              visible={chatOpen}
              onClose={() => setChatOpen(false)}
            />
          </div>
        </main>
      ) : (
        <main className="main">
          <TaskList
            tasks={tasks}
            overdueTasks={overdueTasks}
            viewMode={viewMode}
            selectedDate={selectedDate}
            todayStr={todayStr}
            onViewModeChange={setViewMode}
            onDateChange={setSelectedDate}
            onTasksUpdate={handleTasksUpdate}
          />
          <ChatInterface onTasksUpdate={handleTasksUpdate} collapsed={chatCollapsed} onToggleCollapse={handleToggleChat} />
        </main>
      )}
      {quickEntryOpen && (
        <QuickEntry
          onClose={() => setQuickEntryOpen(false)}
          onTasksUpdate={handleTasksUpdate}
        />
      )}
    </div>
  );
}

export default App;
