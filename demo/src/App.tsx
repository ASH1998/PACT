import { Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import Overview from './pages/Overview'
import Runs from './pages/Runs'
import RunDetail from './pages/RunDetail'
import Agents from './pages/Agents'
import Replay from './pages/Replay'
import TrustArchitecture from './pages/TrustArchitecture'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Layout />}>
        <Route index element={<Overview />} />
        <Route path="runs" element={<Runs />} />
        <Route path="runs/:runId" element={<RunDetail />} />
        <Route path="runs/:runId/replay" element={<Replay />} />
        <Route path="agents" element={<Agents />} />
        <Route path="trust" element={<TrustArchitecture />} />
      </Route>
    </Routes>
  )
}
