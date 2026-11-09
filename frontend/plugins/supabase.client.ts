import { createClient } from '@supabase/supabase-js'

export default defineNuxtPlugin(() => {
  const { public: config } = useRuntimeConfig()
  const supabase = createClient(config.supabaseUrl, config.supabaseAnonKey)

  const session = useState('session', () => null as Awaited<ReturnType<typeof getSession>>)
  async function getSession() {
    return (await supabase.auth.getSession()).data.session
  }
  getSession().then((s) => { session.value = s })
  supabase.auth.onAuthStateChange((_event, s) => { session.value = s })

  return { provide: { supabase } }
})
