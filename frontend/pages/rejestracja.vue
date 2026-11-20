<template>
  <UForm :state="state" class="space-y-4" @submit="onSubmit">
    <UFormGroup label="email:" name="email">
      <UInput v-model="state.email" type="email" autocomplete="email" required />
    </UFormGroup>
    <UFormGroup label="hasło:" name="password">
      <UInput v-model="state.password" type="password" autocomplete="new-password" required />
    </UFormGroup>
    <UFormGroup label="nazwa użytkownika:" name="username">
      <UInput v-model="state.username" autocomplete="nickname" required />
    </UFormGroup>
    <p v-if="error" class="text-red-500 text-sm">
      {{ error }}
    </p>
    <div class="flex gap-2">
      <UButton type="submit" :loading="loading">
        Zarejestruj się
      </UButton>
      <UButton variant="link" to="/">
        Masz już konto? Zaloguj się
      </UButton>
    </div>
  </UForm>
</template>

<script setup lang="ts">
const api = useApi()
const { signIn } = useAuth()

const state = reactive({ email: '', password: '', username: '' })
const error = ref('')
const loading = ref(false)

const ERRORS: Record<string, string> = {
  email_taken: 'Ten adres email jest już zarejestrowany',
  username_taken: 'Ta nazwa użytkownika jest już zajęta',
  weak_password: 'Hasło jest zbyt słabe'
}

async function onSubmit() {
  error.value = ''
  loading.value = true
  try {
    await api('/auth/register', {
      method: 'POST',
      body: {
        email: state.email.trim(),
        password: state.password,
        username: state.username
      }
    })
    if (!(await signIn(state.email.trim(), state.password))) {
      await navigateTo('/')
      return
    }
    await navigateTo('/panel')
  } catch (e) {
    const detail = apiErrorDetail(e)
    if (apiErrorStatus(e) === 422 && !detail) error.value = 'Sprawdź poprawność danych (hasło min. 6 znaków)'
    else error.value = (detail && ERRORS[detail]) || 'Rejestracja nie powiodła się, spróbuj ponownie'
  } finally {
    loading.value = false
  }
}
</script>
