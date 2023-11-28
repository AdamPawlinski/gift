<template>
  <div class="flex flex-col items-center align-middle w-full h-full">
    <div class="flex flex-end my-10">
      <UButton @click="onClickStartLotteryHandler(false)">
        Start lottery
      </UButton>
    </div>
    <div>      
      <div class="flex w-full h-full flex-col justify-center content-center">
        <UForm :state="formState" @submit="onClickSubmitHandler">
          <UFormGroup class="ml-2 text-bold" label="Imię" name="name">
            <UInput class="mt-2" id="name" placeholder="First name" @change="setName"/>
          </UFormGroup>
          <UButton 
            class="my-4 border-green-400"
            :ui="{variant: 'outline'}"
            type="submit"
          >
            Sprawdź kogo wylosowałeś
          </UButton>
        </UForm>
        
        <UModal v-model="showModalLottery">
          <UCard v-if="!changeModal">
            <template #header>
              Czy chcesz rozpocząć nowe losowanie?
            </template>
              <UButton @click="onClickStartLotteryHandler(true)" class="mr-4">
                Tak
              </UButton>
              
              <UButton @click="showModalLottery = false" class="mr-4">
                Nie
              </UButton>
            <template #footer>
              <UButton @click="showModalLottery = false">
                Cancel
              </UButton>
            </template>
          </UCard>
          <UCard v-else>
            <template #header>
              The lottery is finished 
            </template>
            <UButton @click="showModalLottery = false">
                Ok
            </UButton>
            <template #footer>
              <UButton @click="showModalLottery = false">
                Cancel
              </UButton>
            </template>
            <UButton @click="showModalLottery = false" />
          </UCard>
        </UModal>
        <UModal :is-open="showModalResult">
          <UCard>
            <template #header>
              Wylosowałaś/eś
            </template>
            <div>{{drawPick}}</div>
            <template #footer>
              <UButton @click="showModalResult = false">
                Cancel
              </UButton>
            </template>
            <UButton @click="showModalResult = false" />
          </UCard>
        </UModal>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import draw from '../../script/draw.js';
import showResults from '../../script/drawResults.js';
  
  const showModalLottery = ref(false);
  const showModalResult = ref(false);
  const results = ref([]);
  const person = ref('');
  const changeModal = ref(false)
  const drawPick = ref('');
  const formState = reactive({
    email: undefined,
  })

  const client = useSupabaseClient()

  const { data: participants, error } = await useAsyncData('participants', async () => client.from('participants').select('users'))

  const onClickSubmitHandler = () => {
    drawPick.value = showResults(results.value, person);
    showModalResult.value = true;
  };

  const onClickStartLotteryHandler = (startLottery: boolean) => {      
    if (!startLottery) {
      showModalLottery.value = true
    } else {
      results.value = [];
      results.value = draw(participants?.value?.data); 
      console.log(results.value);
      return changeModal.value = true;
    }
  };

  const setName = (e) => {
    console.log(e.target.value)
    person.value = e.target.value;
  }

</script>
