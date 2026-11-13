export function Spark({ points, tone = 'bad' }: { points: number[]; tone?: 'bad' | 'accent' }) {
  const max = Math.max(...points)
  const min = Math.min(...points)
  const pts = points.map((p, i) => `${(i / (points.length - 1)) * 100},${30 - ((p - min) / (max - min || 1)) * 26}`).join(' ')
  return (
    <svg viewBox="0 0 100 32" preserveAspectRatio="none" className={`h-10 w-full ${tone === 'bad' ? 'text-bad' : 'text-accent'}`} aria-hidden>
      <polyline points={pts} fill="none" stroke="currentColor" strokeWidth="2" vectorEffect="non-scaling-stroke" strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  )
}

// Per-variant practice-run data: before[] then after[] response times in ms.
const variantProfiles: Record<string, { before: number[]; after: number[]; maxY: number }> = {
  risky: {
    before: [3800, 3950, 4100, 4050, 3900, 4200, 4150, 4000],
    after:  [520,  430,  390,  360,  340,  355,  345,  340],
    maxY: 4500,
  },
  default: {
    before: [2290, 2410, 2330, 2380, 2300, 2420, 2340, 2370],
    after:  [310,  220,  200,  190,  185,  195,  190,  188],
    maxY: 2500,
  },
}

// Response time during the practice run: high before the fix, low after.
export function PracticeChart({ variant = 'default' }: { variant?: string }) {
  const profile = variantProfiles[variant] ?? variantProfiles['default']
  const { before, after, maxY } = profile
  const all = [...before, ...after]
  const x = (i: number) => (i / (all.length - 1)) * 400
  const y = (v: number) => 112 - (v / maxY) * 100
  const line = all.map((v, i) => `${i === 8 ? 'L' : i === 0 ? 'M' : 'L'}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(' ')
  const area = `${line} L400,112 L0,112 Z`
  const mid = (x(7) + x(8)) / 2
  const beforeAvg = Math.round(before.reduce((s, v) => s + v, 0) / before.length)
  const afterAvg = Math.round(after.reduce((s, v) => s + v, 0) / after.length)
  return (
    <div>
      <div className="relative">
        <svg viewBox="0 0 400 120" preserveAspectRatio="none" className="aspect-[4/1] max-h-40 min-h-24 w-full" role="img" aria-label={`Response time dropped from about ${beforeAvg.toLocaleString()} ms to about ${afterAvg} ms after the fix`}>
          <defs>
            <linearGradient id="pc" x1="0" x2="0" y1="0" y2="1">
              <stop offset="0" stopColor="#8b93ff" stopOpacity="0.28" />
              <stop offset="1" stopColor="#8b93ff" stopOpacity="0" />
            </linearGradient>
          </defs>
          {[20, 60, 100].map((g) => (
            <line key={g} x1="0" x2="400" y1={g} y2={g} stroke="#1f2837" strokeWidth="1" vectorEffect="non-scaling-stroke" />
          ))}
          <path d={area} fill="url(#pc)" />
          <path d={line} fill="none" stroke="#8b93ff" strokeWidth="2.25" vectorEffect="non-scaling-stroke" strokeLinejoin="round" />
          <line x1={mid} x2={mid} y1="0" y2="112" stroke="#8b95a9" strokeDasharray="3 4" strokeWidth="1" vectorEffect="non-scaling-stroke" />
        </svg>
      </div>
      <div className="mt-2 flex text-[12px] text-faint">
        <span className="flex-1">Before fix</span>
        <span className="flex-1 text-right">After fix</span>
      </div>
    </div>
  )
}
