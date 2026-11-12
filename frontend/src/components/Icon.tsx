const paths: Record<string, React.ReactNode> = {
  alert: <><path d="M12 3 2.5 20h19L12 3Z" /><path d="M12 10v4.5M12 17.5v.01" /></>,
  search: <><circle cx="11" cy="11" r="6.5" /><path d="m20 20-4.2-4.2" /></>,
  bulb: <><path d="M9 18h6M10 21h4" /><path d="M12 3a6 6 0 0 0-3.5 10.9c.6.5 1 1.2 1 2V16h5v-.1c0-.8.4-1.5 1-2A6 6 0 0 0 12 3Z" /></>,
  wrench: <path d="M14.7 6.3a4 4 0 0 0 5 5L21 12.6 12.6 21a2.1 2.1 0 0 1-3-3l8.4-8.4M14.7 6.3 17 4l3 3-2.3 2.3" />,
  shield: <><path d="M12 3 4.5 6v6c0 4.5 3 7.7 7.5 9 4.5-1.3 7.5-4.5 7.5-9V6L12 3Z" /><path d="m9 12 2.2 2.2L15.5 10" /></>,
  check: <path d="m5 12.5 4.5 4.5L19 7.5" />,
  chevron: <path d="m6 9 6 6 6-6" />,
  arrow: <path d="M5 12h14M13 6l6 6-6 6" />,
  code: <path d="m8 8-4 4 4 4M16 8l4 4-4 4M13.5 5l-3 14" />,
  logs: <><path d="M5 4h14v16H5z" /><path d="M8.5 9h7M8.5 12.5h7M8.5 16h4" /></>,
  chart: <path d="M4 20V4M4 20h16M8 15l3.5-4 3 2.5L19 8" />,
  history: <><path d="M4 12a8 8 0 1 0 2.5-5.8L4 8.5" /><path d="M4 4v4.5h4.5M12 8v4.5l3 1.5" /></>,
  flask: <><path d="M9.5 3h5M10.5 3v6L5 18.5A1.5 1.5 0 0 0 6.3 21h11.4a1.5 1.5 0 0 0 1.3-2.5L13.5 9V3" /><path d="M7.5 15h9" /></>,
  undo: <path d="M9 14 4 9l5-5M4 9h10a6 6 0 0 1 0 12h-3" />,
  x: <path d="M6 6l12 12M18 6 6 18" />,
  lock: <><rect x="5" y="10.5" width="14" height="10" rx="2.5" /><path d="M8.5 10.5V8a3.5 3.5 0 0 1 7 0v2.5" /></>,
  user: <><circle cx="12" cy="8.5" r="3.5" /><path d="M5 20c.8-3.6 3.6-5.5 7-5.5s6.2 1.9 7 5.5" /></>,
  pulse: <path d="M3 12h4l2.5-6 4 12 2.5-6H21" />,
  clock: <><circle cx="12" cy="12" r="8.5" /><path d="M12 7.5V12l3 2" /></>,
  plus: <path d="M12 5v14M5 12h14" />,
  minus: <path d="M5 12h14" />,
  play: <path d="M8 5.5v13l10.5-6.5L8 5.5Z" />,
  database: <><ellipse cx="12" cy="6" rx="7" ry="3" /><path d="M5 6v6c0 1.7 3.1 3 7 3s7-1.3 7-3V6M5 12v6c0 1.7 3.1 3 7 3s7-1.3 7-3v-6" /></>,
  target: <><circle cx="12" cy="12" r="8" /><circle cx="12" cy="12" r="3.5" /></>,
  file: <><path d="M6 3h8l4 4v14H6z" /><path d="M14 3v4h4M9 12h6M9 16h6" /></>,
  logout: <path d="M10 4H6a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h4M15 8l4 4-4 4M19 12H9" />,
  info: <><circle cx="12" cy="12" r="8.5" /><path d="M12 11v5M12 8v.01" /></>,
}

export function Icon({ name, size = 18, className = '', stroke = 1.7 }: { name: keyof typeof paths | string; size?: number; className?: string; stroke?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={stroke} strokeLinecap="round" strokeLinejoin="round" className={className} aria-hidden>
      {paths[name]}
    </svg>
  )
}

export function Logo({ size = 32 }: { size?: number }) {
  return (
    <div style={{ width: size, height: size }} className="grid place-items-center rounded-[10px] bg-accent/15 text-accent ring-1 ring-accent/30">
      <Icon name="pulse" size={size * 0.58} stroke={1.9} />
    </div>
  )
}
