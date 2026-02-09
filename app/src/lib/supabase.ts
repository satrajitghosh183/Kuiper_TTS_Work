// Supabase client with graceful fallback if not configured
let supabaseClient: any = null

try {
  const supabaseUrl = import.meta.env.VITE_SUPABASE_URL
  const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY

  if (supabaseUrl && supabaseAnonKey) {
    // Dynamic import to avoid errors if @supabase/supabase-js is not installed
    import('@supabase/supabase-js').then(({ createClient }) => {
      supabaseClient = createClient(supabaseUrl, supabaseAnonKey)
    }).catch(() => {
      console.warn('Supabase client library not installed. State sync will be local-only.')
    })
  }
} catch (error) {
  console.warn('Supabase not configured. State sync will be local-only.')
}

export const supabase = supabaseClient

// Auth helpers (with fallbacks)
export const signIn = async (email: string, password: string) => {
  if (!supabase) throw new Error('Supabase not configured')
  const { data, error } = await supabase.auth.signInWithPassword({ email, password })
  if (error) throw error
  return data
}

export const signUp = async (email: string, password: string) => {
  if (!supabase) throw new Error('Supabase not configured')
  const { data, error } = await supabase.auth.signUp({ email, password })
  if (error) throw error
  return data
}

export const signOut = async () => {
  if (!supabase) return
  const { error } = await supabase.auth.signOut()
  if (error) throw error
}

export const getCurrentUser = async () => {
  if (!supabase) return null
  const { data: { user } } = await supabase.auth.getUser()
  return user
}

export const isSupabaseConfigured = () => supabase !== null
