export default defineNuxtRouteMiddleware(async (to) => {
  const loggedIn = await useAuth().isLoggedIn()
  const isPublic = to.path === '/' || to.path === '/rejestracja'

  if (!loggedIn && !isPublic) return navigateTo('/')
  if (loggedIn && isPublic) return navigateTo('/panel')
})
