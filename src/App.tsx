import { NavProvider, useNav } from './nav'
import { Alert } from './screens/Alert'
import { Decision } from './screens/Decision'
import { Fix } from './screens/Fix'
import { Frames } from './screens/Frames'
import { Investigate } from './screens/Investigate'
import { Login } from './screens/Login'
import { Profile } from './screens/Profile'
import { Success } from './screens/Success'
import { Theories } from './screens/Theories'

const screens = { login: Login, alert: Alert, investigate: Investigate, theories: Theories, fix: Fix, decision: Decision, success: Success, profile: Profile, frames: Frames }

function Screen() {
  const { route } = useNav()
  const Current = screens[route]
  return <Current key={route} />
}

// No fixed page size: the app fills the viewport. The wrapper is the query container,
// so screens switch layout at 640 (tablet) and 1024 (laptop) of the available width.
export default function App() {
  return (
    <NavProvider>
      <div className="@container h-dvh w-full">
        <Screen />
      </div>
    </NavProvider>
  )
}
