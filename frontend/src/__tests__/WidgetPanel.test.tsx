// Tests for #88: Widget panel (flag ON)
import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import WidgetPanel from '../components/WidgetPanel'
import ProgressRing from '../components/ProgressRing'
import { TASK_A, TASK_B, TASK_DONE, TODAY } from '../test/fixtures/tasks'

const defaultProps = {
  tasks: [TASK_A, TASK_B, TASK_DONE],
  selectedDate: TODAY,
  onOpenChat: vi.fn(),
}

describe('ProgressRing', () => {
  it('renders correct percentage for done/total', () => {
    const { container } = render(<ProgressRing done={3} total={10} />)
    expect(screen.getByText('30%')).toBeInTheDocument()
    const arc = container.querySelectorAll('circle')[1]
    expect(arc).toBeInTheDocument()
  })

  it('renders 0% when total is 0', () => {
    render(<ProgressRing done={0} total={0} />)
    expect(screen.getByText('0%')).toBeInTheDocument()
  })

  it('renders 100% when done equals total', () => {
    render(<ProgressRing done={5} total={5} />)
    expect(screen.getByText('100%')).toBeInTheDocument()
  })
})

describe('WidgetPanel', () => {
  beforeEach(() => {
    defaultProps.onOpenChat.mockReset()
  })

  it('renders the Dashboard header', () => {
    render(<WidgetPanel {...defaultProps} />)
    expect(screen.getByText(/dashboard/i)).toBeInTheDocument()
  })

  it('renders Ask AI button', () => {
    render(<WidgetPanel {...defaultProps} />)
    expect(screen.getByRole('button', { name: /ask ai/i })).toBeInTheDocument()
  })

  it('Ask AI button calls onOpenChat', async () => {
    const user = userEvent.setup()
    render(<WidgetPanel {...defaultProps} />)
    await user.click(screen.getByRole('button', { name: /ask ai/i }))
    expect(defaultProps.onOpenChat).toHaveBeenCalledTimes(1)
  })

  it("renders Today's Progress widget", () => {
    render(<WidgetPanel {...defaultProps} />)
    expect(screen.getByTestId('widget-progress')).toBeInTheDocument()
  })

  it('progress ring shows 1/3 done (TASK_DONE is completed, TASK_A and TASK_B are not)', () => {
    render(<WidgetPanel {...defaultProps} />)
    // ProgressRing should show 33% (1 of 3 today tasks)
    expect(screen.getByText('33%')).toBeInTheDocument()
  })

  it('renders Next Up widget showing first uncompleted timed task', () => {
    render(<WidgetPanel {...defaultProps} />)
    const widget = screen.getByTestId('widget-next-up')
    expect(widget).toBeInTheDocument()
    // TASK_A is at 10:00, TASK_B at 14:00; next up should be TASK_A
    expect(screen.getByText(TASK_A.title)).toBeInTheDocument()
  })

  it('renders This Week bar chart with 7 bars', () => {
    const { container } = render(<WidgetPanel {...defaultProps} />)
    const bars = container.querySelectorAll('.widget-week-bar')
    expect(bars.length).toBe(7)
  })

  it('renders This Week widget', () => {
    render(<WidgetPanel {...defaultProps} />)
    expect(screen.getByTestId('widget-week')).toBeInTheDocument()
  })
})
