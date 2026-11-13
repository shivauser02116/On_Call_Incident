import { Icon, Logo } from '../components/Icon'
import { useNav } from '../nav'
import { DemoTag } from '../components/ui'

function Field({ label, icon, type, placeholder, error, defaultValue }: { label: string; icon: string; type: string; placeholder: string; error?: boolean; defaultValue?: string }) {
  return (
    <label className="block">
      <span className="mb-2 block text-[13px] font-medium text-ink/90">{label}</span>
      <span
        className={`flex h-12 items-center gap-3 rounded-xl border bg-bg px-4 focus-within:ring-4 ${
          error ? 'border-bad/60 text-bad focus-within:ring-bad/10' : 'border-line text-mute focus-within:border-accent/60 focus-within:ring-accent/10'
        }`}
      >
        <Icon name={icon} size={18} />
        <input type={type} defaultValue={defaultValue} placeholder={placeholder} aria-invalid={error} className="h-full min-w-0 flex-1 bg-transparent text-[15px] text-ink outline-none placeholder:text-faint" />
      </span>
    </label>
  )
}

export function Login() {
  const { go, variant } = useNav()
  const error = variant === 'error'
  return (
    <div className="relative flex h-full flex-col overflow-y-auto bg-bg">
      <div className="pointer-events-none absolute left-1/2 top-[-12rem] aspect-square w-[120%] max-w-[34rem] -translate-x-1/2 rounded-full bg-accent/[0.09] blur-[110px]" />
      <div className="screen-in relative m-auto flex w-full max-w-md flex-col items-center px-4 py-10">
        <Logo size={52} />
        <h1 className="mt-6 text-center text-[26px] font-semibold tracking-tight @tablet:text-[30px]">OnCall Rehearsal Agent</h1>
        <p className="mt-2 text-center text-[15px] text-mute">Sign in to see what happened and what to do next.</p>

        <form className="mt-8 w-full space-y-5 rounded-3xl border border-line bg-panel p-6 @tablet:p-8" onSubmit={(e) => { e.preventDefault(); go('alert') }}>
          {error && (
            <div role="alert" className="flex items-start gap-3 rounded-xl border border-bad/30 bg-bad/10 px-4 py-3 text-[13.5px] leading-snug text-bad">
              <Icon name="info" size={18} className="mt-px shrink-0" />
              <span>That username or password doesn’t match. Check them and try again.</span>
            </div>
          )}
          <Field label="Username" icon="user" type="text" placeholder="maya.reyes" error={error} defaultValue={error ? 'maya.reyes' : undefined} />
          <Field label="Password" icon="lock" type="password" placeholder="Enter your password" error={error} defaultValue={error ? 'wrongpassword' : undefined} />
          <button type="submit" className="h-12 w-full rounded-xl bg-accent text-[15px] font-semibold text-bg shadow-[0_10px_28px_-10px_rgba(139,147,255,0.9)] hover:bg-accent-strong">Sign In</button>
        </form>

        <div className="mt-7 flex items-center gap-2.5 text-[13px] text-mute">
          <Icon name="shield" size={16} className="text-accent" />
          The agent investigates. You decide.
        </div>
        <div className="mt-6"><DemoTag /></div>
      </div>
    </div>
  )
}
