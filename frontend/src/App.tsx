import { BrowserRouter as Router, Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import Agents from './pages/Agents'
import Bets from './pages/Bets'
import Analysis from './pages/Analysis'
import Settings from './pages/Settings'
import CollegeBasketball from './pages/CollegeBasketball'
import Parlays from './pages/Parlays'

function App() {
  return (
    <Router>
      <Layout>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/bets" element={<Bets />} />
          <Route path="/college-basketball" element={<CollegeBasketball />} />
          <Route path="/agents" element={<Agents />} />
          <Route path="/analysis" element={<Analysis />} />
          <Route path="/settings" element={<Settings />} />
          <Route path="/parlays" element={<Parlays />} />
        </Routes>
      </Layout>
    </Router>
  )
}

export default App

