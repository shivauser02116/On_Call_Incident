import { Icon } from '../components/Icon'

// Review page: shows the live app inside simulated devices so laptop and phone states can be
// compared side by side. The app inside has no fixed size; only these preview windows do.
const base = () => window.location.pathname

function Device({ label, hash, kind }: { label: string; hash: string; kind: 'laptop' | 'mobile' }) {
  return (
    <figure className={kind === 'laptop' ? 'w-full max-w-6xl' : 'w-full max-w-[24.375rem]'}>
      <figcaption className="mb-2.5 text-[12.5px] text-faint">{label}</figcaption>
      <iframe
        title={label}
        src={`${base()}#${hash}`}
        className={`w-full rounded-2xl bg-bg ring-1 ring-line shadow-[0_30px_80px_-30px_rgba(0,0,0,0.9)] ${kind === 'laptop' ? 'aspect-[8/5]' : 'aspect-[39/84]'}`}
      />
    </figure>
  )
}

export function Frames() {
  return (
    <div className="h-full overflow-y-auto px-6 py-10 @laptop:px-12">
      <div className="mx-auto flex max-w-6xl flex-col gap-12">
        <header>
          <h1 className="flex items-center gap-3 text-[22px] font-semibold tracking-tight"><Icon name="pulse" size={22} className="text-accent" /> OnCall Rehearsal Agent · new frames</h1>
          <p className="mt-1 text-[14px] text-mute">Live previews. Open the app without #frames to use the full prototype.</p>
        </header>
        <section className="flex flex-col gap-4">
          <h2 className="text-[16px] font-semibold">7 · Profile</h2>
          <Device label="Laptop" hash="profile" kind="laptop" />
          <div className="mt-4 flex flex-wrap items-start gap-8"><Device label="Mobile" hash="profile" kind="mobile" /></div>
        </section>
        <section className="flex flex-col gap-4">
          <h2 className="text-[16px] font-semibold">Alert - menu open</h2>
          <Device label="Laptop" hash="alert-menu" kind="laptop" />
          <div className="mt-4 flex flex-wrap items-start gap-8"><Device label="Mobile · bottom sheet" hash="alert-menu" kind="mobile" /></div>
        </section>
      </div>
    </div>
  )
}
