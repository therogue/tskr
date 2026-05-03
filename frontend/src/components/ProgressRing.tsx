// SVG progress ring component mirroring HTML mockup lines 415-429.

interface ProgressRingProps {
  done: number
  total: number
  size?: number
  strokeWidth?: number
}

function ProgressRing({ done, total, size = 72, strokeWidth = 6 }: ProgressRingProps) {
  const radius = (size - strokeWidth) / 2
  const circumference = 2 * Math.PI * radius
  const fraction = total > 0 ? Math.min(1, done / total) : 0
  const dashOffset = circumference * (1 - fraction)
  const pct = total > 0 ? Math.round((done / total) * 100) : 0

  return (
    <svg
      width={size}
      height={size}
      viewBox={`0 0 ${size} ${size}`}
      className="progress-ring"
      aria-label={`${pct}% complete`}
    >
      {/* Track */}
      <circle
        cx={size / 2}
        cy={size / 2}
        r={radius}
        fill="none"
        stroke="var(--border, #2a3f5f)"
        strokeWidth={strokeWidth}
      />
      {/* Progress arc */}
      <circle
        cx={size / 2}
        cy={size / 2}
        r={radius}
        fill="none"
        stroke="var(--accent, #6b8cce)"
        strokeWidth={strokeWidth}
        strokeDasharray={circumference}
        strokeDashoffset={dashOffset}
        strokeLinecap="round"
        transform={`rotate(-90 ${size / 2} ${size / 2})`}
      />
      {/* Center text */}
      <text
        x={size / 2}
        y={size / 2}
        textAnchor="middle"
        dominantBaseline="middle"
        fontSize="13"
        fontWeight="700"
        fill="var(--text, #e8e8e8)"
      >
        {pct}%
      </text>
    </svg>
  )
}

export default ProgressRing
