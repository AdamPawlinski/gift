<template>
  <div v-if="me" class="space-y-4">
    <h1 class="text-xl font-bold">
      Witaj {{ me.username }}
    </h1>

    <div class="flex flex-wrap gap-2">
      <UButton
        :disabled="!me.is_master || lottery?.status === 'finished'"
        @click="confirm = 'start'"
      >
        Uruchom losowanie
      </UButton>
      <UButton
        color="red"
        variant="outline"
        :disabled="!me.is_master || lottery?.status !== 'finished'"
        @click="confirm = 'cancel'"
      >
        Kasuj wyniki losowania
      </UButton>
    </div>

    <p v-if="me.is_master" class="text-sm text-gray-500">
      Uczestnicy ({{ participants.length }}): {{ participants.map(p => p.username).join(', ') }}
    </p>

    <div v-if="lottery">
      <p v-if="lottery.status === 'not_started'">
        Twoje losowanie jeszcze się nie zaczęło
      </p>
      <div v-else-if="lottery.participated" class="space-y-2">
        <p>Oto wyniki Twojego losowania</p>
        <p class="font-semibold">
          Wylosowałeś/aś {{ lottery.receiver_username }}. Pomyśl o jakimś prezencie.
        </p>
        <UButton :loading="sending" @click="sendEmail">
          Wyślij wynik na swój adres mailowy
        </UButton>
      </div>
      <p v-else>
        Losowanie odbyło się przed Twoją rejestracją. Poproś mistrza losowania o ponowne losowanie.
      </p>
    </div>

    <UButton variant="outline" @click="logout">
      Wyloguj się
    </UButton>

    <UModal :model-value="confirm !== null" @update:model-value="confirm = null">
      <UCard>
        <template #header>
          {{ confirm === 'start' ? 'Czy na pewno uruchomić losowanie?' : 'Czy na pewno skasować wyniki losowania?' }}
        </template>
        <div class="flex gap-2">
          <UButton :loading="busy" @click="confirm === 'start' ? startLottery() : cancelLottery()">
            Tak
          </UButton>
          <UButton variant="outline" @click="confirm = null">
            Nie
          </UButton>
        </div>
      </UCard>
    </UModal>
  </div>
</template>

<script setup lang="ts">
interface Me { id: string, username: string, email: string, is_master: boolean }
interface Lottery {
  status: 'not_started' | 'finished'
  lottery_id: string | null
  participated: boolean
  receiver_username: string | null
}

const api = useApi()
const { signOut } = useAuth()
const toast = useToast()

const me = ref<Me | null>(null)
const lottery = ref<Lottery | null>(null)
const participants = ref<{ username: string }[]>([])
const confirm = ref<'start' | 'cancel' | null>(null)
const busy = ref(false)
const sending = ref(false)

const ERRORS: Record<string, string> = {
  not_enough_participants: 'Za mało uczestników (min. 3)',
  lottery_active: 'Losowanie już się odbyło',
  no_active_lottery: 'Brak aktywnego losowania',
  rate_limited: 'Spróbuj ponownie za kilka minut',
  email_failed: 'Nie udało się wysłać wiadomości'
}

function showError(e: unknown) {
  const detail = apiErrorDetail(e)
  toast.add({ title: (detail && ERRORS[detail]) || 'Coś poszło nie tak, spróbuj ponownie', color: 'red' })
}

async function load() {
  me.value = await api<Me>('/me')
  lottery.value = await api<Lottery>('/lottery/current')
  participants.value = me.value.is_master ? await api('/participants') : []
}

onMounted(async () => {
  try {
    await load()
  } catch (e) {
    if (apiErrorStatus(e) === 401) await logout()
    else showError(e)
  }
})

async function run(action: () => Promise<unknown>) {
  busy.value = true
  try {
    await action()
    await load()
  } catch (e) {
    showError(e)
  } finally {
    busy.value = false
    confirm.value = null
  }
}

const startLottery = () => run(() => api('/lottery', { method: 'POST' }))
const cancelLottery = () => run(() => api('/lottery/current', { method: 'DELETE' }))

async function sendEmail() {
  sending.value = true
  try {
    await api('/lottery/current/email', { method: 'POST' })
    toast.add({ title: `Wysłano wynik na ${me.value?.email}` })
  } catch (e) {
    showError(e)
  } finally {
    sending.value = false
  }
}

async function logout() {
  await signOut()
  await navigateTo('/')
}
</script>
