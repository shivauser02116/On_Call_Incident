import { NavProvider, useNav } from './nav'
import { Alert } from './screens/Alert'
import { Decision } from './screens/Decision'
import { Fix } from './screens/Fix'
import { Investigate } from './screens/Investigate'
import { Login } from './screens/Login'
import { Profile } from './screens/Profile'
import { Stopwatch } from './screens/Stopwatch'
import { Success } from './screens/Success'
import { Theories } from './screens/Theories'

const screens = {
  login: Login,
  alert: Alert,
  investigate: Investigate,
  theories: Theories,
  fix: Fix,
  decision: Decision,
  success: Success,
  profile: Profile,
  stopwatch: Stopwatch,
}

function Screen() {
  const { route } = useNav()
  const Current = screens[route] || Login
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
