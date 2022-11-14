<template>
  <div>
    <CBox 
      my="3"
      d="flex"
      justify-content="flex-end"
    >
      <CButton mr="3" @click="onClickStartLotteryHandler">
        Start lottery
      </CButton>
      <CIconButton
        mr="3"
        :icon="colorMode === 'light' ? 'moon' : 'sun'"
        :aria-label="`Switch to ${
          colorMode === 'light' ? 'dark' : 'light'
        } mode`"
        @click="toggleColorMode"
      />
    </CBox>
    <CBox
      v-bind="mainStyles[colorMode]"
      d="flex"
      w="100vw"
      h="95vh"
      flex-dir="column"
      justify-content="center"
    >      
      <CHeading text-align="center" mb="4">
        Christmas gifts lottery
      </CHeading>
      <CFlex justify="center" direction="column" align="center">
        <CFormControl is-required >
          <CFormLabel for="fname">Imię</CFormLabel>
          <CInput id="fname" placeholder="First name" @change.prevent="setName"/>
          <CFormLabel for="sname">Nazwisko</CFormLabel>
          <CInput id="sname" placeholder="Last name" />
          <CButton
            loading-text="Submitting"
            variant-color="blue"
            variant="outline"
            my="4"
            type="submit"
            @click="onClickSubmitHandler"  
          >
            Sprawdź kogo wylosowałeś
          </CButton>
        </CFormControl>
        
        <CModal :is-open="showModal">
          <CModalOverlay />
          <CModalContent>
            <CModalHeader>The lottery is finished</CModalHeader>
            <CModalFooter>
              <CButton @click="showModal = false">
                Cancel
              </CButton>
            </CModalFooter>
            <CModalCloseButton @click="showModal = false" />
          </CModalContent>
        </CModal>
        <CModal :is-open="!!drawPick">
          <CModalOverlay />
          <CModalContent>
            <CModalHeader>Wylosowałaś/eś</CModalHeader>
            <CModalBody>{{drawPick}}</CModalBody>
            <CModalFooter>
              <CButton @click="showModal = false">
                Cancel
              </CButton>
            </CModalFooter>
            <CModalCloseButton @click="showModal = false" />
          </CModalContent>
        </CModal>
      </CFlex>
    </CBox>
  </div>
</template>

<script lang="js">
import {
  CBox,
  CButton,
  CModal,
  CModalContent,
  CModalOverlay,
  CModalHeader,
  CModalFooter,
  CModalBody,
  CModalCloseButton,
  CIconButton,
  CFlex,
  CHeading,
  CFormControl,
  CFormLabel,
  CFormErrorMessage,
  CFormHelperText,
  CInput,
} from '@chakra-ui/vue'
import draw from '../script/draw.js';
import showResults from '../script/drawResults.js';
export default {
  name: 'IndexPage',
  components: {
    CBox,
    CButton,
    CModal,
    CModalContent,
    CModalOverlay,
    CModalHeader,
    CModalFooter,
    CModalBody,
    CModalCloseButton,
    CIconButton,
    CFlex,
    CHeading
  },
  inject: ['$chakraColorMode', '$toggleColorMode'],
  data () {
    return {
      showModal: false,
      results: [],
      person: '',
      drawPick: '',
      mainStyles: {
        dark: {
          bg: 'gray.700',
          color: 'whiteAlpha.900'
        },
        light: {
          bg: 'white',
          color: 'gray.900'
        }
      }
    }
  },
  computed: {
    colorMode () {
      return this.$chakraColorMode()
    },
    theme () {
      return this.$chakraTheme()
    },
    toggleColorMode () {
      return this.$toggleColorMode
    },
  },
  methods: {
    onClickSubmitHandler() {
      this.drawPick = showResults(this.results, this.person);
    },
    onClickStartLotteryHandler() {      
      this.results = draw();
      this.showModal = true;
      console.log(this.results)
    },
    setName(e) {
      console.log(e.target.value)
      this.person = e.target.value;
    }
  }
}
</script>
