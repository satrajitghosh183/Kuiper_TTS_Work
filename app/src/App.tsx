import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { Layout } from './components/Layout'
import { Welcome } from './pages/Welcome'
import { Setup } from './pages/Setup'
import { Record } from './pages/Record'
import { Train } from './pages/Train'
import { Test } from './pages/Test'

function App() {
  return (
    <BrowserRouter
      future={{
        v7_startTransition: true,
        v7_relativeSplatPath: true,
      }}
    >
      <Layout>
        <Routes>
          <Route path="/" element={<Welcome />} />
          <Route path="/setup" element={<Setup />} />
          <Route path="/record" element={<Record />} />
          <Route path="/train" element={<Train />} />
          <Route path="/test" element={<Test />} />
        </Routes>
      </Layout>
    </BrowserRouter>
  )
}

export default App

