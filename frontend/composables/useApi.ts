export function useApi() {
  const { public: config } = useRuntimeConfig()
  const { $supabase } = useNuxtApp()

  return $fetch.create({
    baseURL: config.apiBase,
    async onRequest({ options }) {
      const { data } = await $supabase.auth.getSession()
      const headers = new Headers(options.headers)
      if (data.session) headers.set('Authorization', `Bearer ${data.session.access_token}`)
      options.headers = headers
    }
  })
}

/** Backend error code (`detail`) of a failed request, e.g. "master_taken". */
export function apiErrorDetail(error: unknown): string | undefined {
  const detail = (error as { data?: { detail?: unknown } })?.data?.detail
  return typeof detail === 'string' ? detail : undefined
}

export function apiErrorStatus(error: unknown): number | undefined {
  return (error as { statusCode?: number })?.statusCode
}
