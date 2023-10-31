<template>
  <div>
    <div 
      my="3"
      d="flex"
      justify-content="flex-end"
    >
      <UButton mr="3" @click="onClickStartLotteryHandler(false)">
        Start lottery
      </UButton>
    </div>
    <div
      d="flex"
      w="100vw"
      h="95vh"
      flex-dir="column"
      justify-content="center"
    >      
      <div text-align="center" mb="4">
        Christmas gifts lottery
      </div>
      <div class="flex flex-col justify-center content-center">
        <UForm>
          <UFormGroup label="Imię" name="name">
            <UInput id="name" placeholder="First name" @change.prevent="setName"/>
          </UFormGroup>
          <!-- <CFormLabel for="sname">Nazwisko</CFormLabel>
          <CInput id="sname" placeholder="Last name" /> -->
          <UButton
            loading-text="Submitting"
            variant-color="blue"
            variant="outline"
            my="4"
            type="submit"
            @click="onClickSubmitHandler"  
          >
            Sprawdź kogo wylosowałeś
          </UButton>
        </UForm>
        
        <UModal :is-open="showModalLottery">
          <UCard v-if="!startLottery">
            <template #header>
              Czy chcesz rozpocząć nowe losowanie?
            </template>
              <UButton @click="onClickStartLotteryHandler(true)">
                Tak
              </UButton>
              
              <UButton @click="showModalLottery = false">
                Nie
              </UButton>
            <template #footer>
              <UButton @click="showModalLottery = false">
                Cancel
              </UButton>
            </template>
            <UButton @click="showModalLottery = false" />
          </UCard>
          <UCard v-else>
            <template #header>
              The lottery is finished 
            </template>
            <template #footer>
              <UButton @click="showModalLottery = false; startLottery = false">
                Cancel
              </UButton>
            </template>
            <UButton @click="showModalLottery = false; startLottery = false" />
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
import draw from '../script/draw.js';
import showResults from '../script/drawResults.js';
  
  const showModalLottery = ref(false);
  const showModalResult = ref(false);
  const startLottery = ref(false);
  const lotteryFinished = ref(false); 
  const results = ref([]);
  const person = ref('');
  const drawPick = ref('');
  const mainStyles = ref({
    dark: {
      bg: 'gray.700',
      color: 'whiteAlpha.900'
    },
    light: {
      bg: 'white',
      color: 'gray.900'
    }
  })

  const onClickSubmitHandler = () => {
    drawPick.value = showResults(results, person);
    showModalResult.value = true;
  };

  const onClickStartLotteryHandler = (startLottery: boolean = false) => {      
    if (!startLottery) {
      showModalLottery.value = true
    } else {
      results.value = [];
      startLottery = true;
      results.value = draw();        
    }
  };

  const setName = (e) => {
    person.value = e.target.value;
  }
</script>
