import { lazy, Suspense } from 'react'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { Layout } from './components/Layout'
import { Loader2 } from 'lucide-react'

// Lazy load pages for code splitting
const Welcome = lazy(() => import('./pages/Welcome').then(m => ({ default: m.Welcome })))
const Setup = lazy(() => import('./pages/Setup').then(m => ({ default: m.Setup })))
const Record = lazy(() => import('./pages/Record').then(m => ({ default: m.Record })))
const Train = lazy(() => import('./pages/Train').then(m => ({ default: m.Train })))
const Test = lazy(() => import('./pages/Test').then(m => ({ default: m.Test })))

// Loading fallback
const PageLoader = () => (
  <div className="flex items-center justify-center min-h-screen">
    <Loader2 className="animate-spin text-accent" size={32} />
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
            <Route path="/" element={<Welcome />} />
            <Route path="/setup" element={<Setup />} />
            <Route path="/record" element={<Record />} />
            <Route path="/train" element={<Train />} />
            <Route path="/test" element={<Test />} />
          </Routes>
        </Suspense>
      </Layout>
    </BrowserRouter>
  )
}

export default App

