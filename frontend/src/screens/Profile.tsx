import { ActionBar, Shell } from '../components/Frame'
import { Icon } from '../components/Icon'
import { Avatar, RoleBadge } from '../components/UserMenu'
import { Card, GhostButton, PageHeader } from '../components/ui'
import { useNav } from '../nav'

export function Profile() {
  const { signOut, currentUser } = useNav()
  const username = currentUser?.username || 'user'
  const role = currentUser?.role || 'Engineer'
  const lastSignIn = currentUser?.last_sign_in || 'Current session'

  return (
    <Shell
      current={-1}
      footer={
        <ActionBar note="Signing out ends your session on this device.">
          <GhostButton className="gap-2" onClick={signOut}>
            <Icon name="logout" size={18} /> Sign out
          </GhostButton>
        </ActionBar>
      }
    >
      <PageHeader eyebrow="Your account" title="Profile" />

      <Card className="w-full max-w-2xl p-5 @laptop:p-8">
        <div className="flex flex-col items-center gap-5 text-center @tablet:flex-row @tablet:text-left">
          <div className="scale-110 @tablet:scale-100">
            <Avatar size="lg" />
          </div>
          <div className="min-w-0">
            <div className="break-words text-[24px] font-semibold leading-tight tracking-tight">{username}</div>
            <div className="mt-2.5 flex items-center justify-center gap-2.5 @tablet:justify-start">
              <RoleBadge role={role} />
              <span className="text-[13.5px] text-mute">{username}</span>
            </div>
          </div>
        </div>

        <dl className="mt-7 divide-y divide-line/70 border-t border-line">
          <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1 py-4">
            <dt className="flex items-center gap-2.5 text-[14px] text-mute">
              <Icon name="clock" size={17} /> Last signed in
            </dt>
            <dd className="text-[14.5px] font-medium">{lastSignIn}</dd>
          </div>
          <div className="flex items-center gap-2.5 py-4 text-[14px] text-mute">
            <span className="size-2 shrink-0 rounded-full bg-ok" />
            Signed in to OnCall Rehearsal Agent
          </div>
        </dl>
      </Card>
    </Shell>
  )
}
