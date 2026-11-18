export function useAuth() {
  const { $supabase } = useNuxtApp()

  async function signIn(email: string, password: string): Promise<boolean> {
    const { error } = await $supabase.auth.signInWithPassword({ email, password })
    return !error
  }

  async function signOut(scope: 'global' | 'local' = 'global') {
    await $supabase.auth.signOut({ scope })
  }

  async function isLoggedIn(): Promise<boolean> {
    return (await $supabase.auth.getSession()).data.session !== null
  }

  return { signIn, signOut, isLoggedIn }
}
