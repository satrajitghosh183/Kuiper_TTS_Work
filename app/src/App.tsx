import { lazy, Suspense } from 'react'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { Layout } from './components/Layout'
import { Record } from './pages/Record'

// Record is eager-loaded so the first screen (training set) opens fast, especially on slow machines
const Welcome = lazy(() => import('./pages/Welcome').then(m => ({ default: m.Welcome })))
const Setup = lazy(() => import('./pages/Setup').then(m => ({ default: m.Setup })))
const Train = lazy(() => import('./pages/Train').then(m => ({ default: m.Train })))
const Test = lazy(() => import('./pages/Test').then(m => ({ default: m.Test })))

// Minimal fallback for lazy routes (no animation to keep old PCs responsive)
const PageLoader = () => (
  <div className="flex items-center justify-center min-h-[40vh] text-text-secondary text-body">
    Loading…
  </div>
)

function App() {
  return (
    <BrowserRouter
      future={{
        v7_startTransition: true,
        v7_relativeSplatPath: true,
      }}
    >
      <Layout>
        <Suspense fallback={<PageLoader />}>
          <Routes>
            <Route path="/" element={<Record />} />
            <Route path="/record" element={<Record />} />
            <Route path="/welcome" element={<Welcome />} />
            <Route path="/setup" element={<Setup />} />
            <Route path="/train" element={<Train />} />
            <Route path="/test" element={<Test />} />
          </Routes>
        </Suspense>
      </Layout>
    </BrowserRouter>
  )
}

export default App

