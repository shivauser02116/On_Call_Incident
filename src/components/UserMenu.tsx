import { useEffect, useRef, useState } from 'react'
import { useNav } from '../nav'
import { Icon } from './Icon'

export const user = { name: 'Maya Reyes', username: 'maya.reyes', initials: 'MR', role: 'Engineer' as 'Engineer' | 'Admin' }

export function Avatar({ size = 'md' }: { size?: 'md' | 'lg' }) {
  return (
    <span className={`grid shrink-0 place-items-center rounded-full bg-accent/15 font-semibold text-accent ring-1 ring-accent/30 ${size === 'lg' ? 'size-20 text-[26px]' : 'size-9 text-[12.5px]'}`}>{user.initials}</span>
  )
}

export function RoleBadge({ role = user.role }: { role?: 'Engineer' | 'Admin' }) {
  return <span className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${role === 'Admin' ? 'bg-warn/15 text-warn' : 'bg-accent/15 text-accent'}`}>{role}</span>
}

function Items({ onPick, tall }: { onPick: (a: 'profile' | 'signout') => void; tall?: boolean }) {
  const row = `flex w-full items-center gap-3 px-4 text-left text-[14.5px] transition-colors ${tall ? 'min-h-14' : 'min-h-11'}`
  return (
    <div role="menu" className="py-1.5">
      <button role="menuitem" onClick={() => onPick('profile')} className={`${row} text-ink hover:bg-panel-2`}>
        <Icon name="user" size={18} className="text-mute" /> View profile
      </button>
      <div role="separator" className="my-1.5 h-px bg-line" />
      <button role="menuitem" onClick={() => onPick('signout')} className={`${row} text-ink hover:bg-panel-2`}>
        <Icon name="logout" size={18} className="text-mute" /> Sign out
      </button>
    </div>
  )
}

/** bar: dropdown for tablet/laptop header. sheet: bottom sheet for the phone stepper. */
export function UserMenu({ mode }: { mode: 'bar' | 'sheet' }) {
  const { go, signOut, variant } = useNav()
  const [open, setOpen] = useState(variant === 'menu')
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const onDown = (e: MouseEvent) => { if (mode === 'bar' && ref.current && !ref.current.contains(e.target as Node)) setOpen(false) }
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpen(false) }
    document.addEventListener('mousedown', onDown)
    document.addEventListener('keydown', onKey)
    return () => { document.removeEventListener('mousedown', onDown); document.removeEventListener('keydown', onKey) }
  }, [open, mode])

  const pick = (a: 'profile' | 'signout') => {
    setOpen(false)
    if (a === 'profile') go('profile')
    else signOut()
  }

  const trigger = (
    <button
      type="button"
      aria-haspopup="menu"
      aria-expanded={open}
      aria-label="Open user menu"
      onClick={() => setOpen((o) => !o)}
      className={
        mode === 'bar'
          ? `flex min-h-11 items-center gap-3 rounded-full py-1 pl-1 pr-1 transition-colors hover:bg-panel-2 @laptop:pr-3 ${open ? 'bg-panel-2' : ''}`
          : 'grid size-11 place-items-center rounded-full'
      }
    >
      <Avatar />
      {mode === 'bar' && (
        <span className="hidden items-center gap-2.5 @laptop:flex">
          <span className="text-[13.5px] font-medium">{user.username}</span>
          <RoleBadge />
          <Icon name="chevron" size={16} className={`text-mute transition-transform ${open ? 'rotate-180' : ''}`} />
        </span>
      )}
    </button>
  )

  if (mode === 'bar') {
    return (
      <div ref={ref} className="relative">
        {trigger}
        {open && (
          <div className="screen-in absolute right-0 top-full z-50 mt-2 min-w-56 overflow-hidden rounded-2xl border border-line bg-panel shadow-[0_24px_60px_-20px_rgba(0,0,0,0.9)]">
            <div className="flex items-center gap-3 border-b border-line px-4 py-3 @laptop:hidden">
              <span className="text-[13.5px] font-medium">{user.username}</span>
              <RoleBadge />
            </div>
            <Items onPick={pick} />
          </div>
        )}
      </div>
    )
  }

  return (
    <>
      {trigger}
      {open && (
        <div className="fixed inset-0 z-50 flex flex-col justify-end">
          <button aria-label="Close menu" onClick={() => setOpen(false)} className="sheet-fade absolute inset-0 bg-black/60" />
          <div className="sheet-up relative rounded-t-3xl border-t border-line bg-panel pb-5 shadow-[0_-24px_60px_-20px_rgba(0,0,0,0.9)]">
            <div className="mx-auto mt-2.5 h-1 w-10 rounded-full bg-line" />
            <div className="flex items-center gap-3 px-5 pb-3 pt-4">
              <Avatar />
              <div className="leading-tight">
                <div className="text-[15px] font-medium">{user.username}</div>
                <div className="mt-1"><RoleBadge /></div>
              </div>
            </div>
            <div className="border-t border-line"><Items onPick={pick} tall /></div>
          </div>
        </div>
      )}
    </>
  )
}
