<template>
  <div>
    <HeroSection />

    <!-- CV + Hasil (tanpa modal) -->
    <CvSection />

    <!-- Modals (satu instance masing-masing): -->
    <MobileResultsModal />
    <OptionsModal />
    <SubscriptionModal />
  </div>
</template>

<script setup lang="ts">
// Auto-import komponen Nuxt biasanya aktif, tapi tetap aman bila pakai ini:
// (Jika Anda memakai auto-import components, baris import bisa dihapus)
import HeroSection from '~/components/HeroSection.vue'
import CvSection from '~/components/CvSection.vue'
import MobileResultsModal from '~/components/MobileResultsModal.vue'
import OptionsModal from '~/components/OptionsModal.vue'
import SubscriptionModal from '~/components/SubscriptionModal.vue'
</script>

