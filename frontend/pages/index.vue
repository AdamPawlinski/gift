<template>
  <UForm :state="state" class="space-y-4" @submit="onSubmit">
    <UFormGroup label="email:" name="email">
      <UInput v-model="state.email" type="email" autocomplete="email" required />
    </UFormGroup>
    <UFormGroup label="hasło:" name="password">
      <UInput v-model="state.password" type="password" autocomplete="current-password" required />
    </UFormGroup>
    <p v-if="failed" class="text-red-500 text-sm">
      Nieudane logowanie, wprowadź prawidłowy adres email i hasło
    </p>
    <div class="flex gap-2">
      <UButton type="submit" :loading="loading">
        Zaloguj się
      </UButton>
      <UButton variant="outline" to="/rejestracja">
        Zarejestruj się
      </UButton>
    </div>
  </UForm>
</template>

<script setup lang="ts">
const { signIn } = useAuth()

const state = reactive({ email: '', password: '' })
const failed = ref(false)
const loading = ref(false)

async function onSubmit() {
  failed.value = false
  loading.value = true
  const ok = await signIn(state.email.trim(), state.password)
  loading.value = false
  if (ok) await navigateTo('/panel')
  else failed.value = true
}
</script>
