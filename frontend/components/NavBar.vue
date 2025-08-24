<template>
  <nav
      ref="navRef"
      role="navigation"
      class="fixed top-0 left-0 right-0 z-50 bg-purple-200/95 backdrop-blur-0
           border-b-4 border-neutral-900
           shadow-[0_10px_0_0_#111]"
  >
    <div class="max-w-6xl mx-auto px-4 md:px-6">
      <div class="h-20 flex items-center justify-between">
        <!-- Logo / Brand -->
        <a href="/" class="inline-flex items-center gap-3">
          <span
              class="grid place-items-center w-10 h-10 md:w-12 md:h-12
                   bg-white rounded-xl
                   border-4 border-neutral-900
                   shadow-[6px_6px_0_0_#111]"
              aria-hidden="true"
          >🤖</span>
          <span class="text-xl md:text-2xl font-black tracking-tight text-neutral-900">
            Loker Kerja
          </span>
        </a>

        <!-- Right: CTA -->
        <div class="flex items-center gap-3">
          <button
              type="button"
              class="bg-white text-neutral-900 px-5 py-3 rounded-xl font-extrabold
                   border-4 border-neutral-900 shadow-[8px_8px_0_0_#111]
                   active:translate-x-1 active:translate-y-1
                   active:shadow-[4px_4px_0_0_#111]"
              @click="scrollToCv"
          >
            Upload CV
          </button>
        </div>
      </div>
    </div>
  </nav>
</template>

<script setup lang="ts">
import { ref } from 'vue'

const navRef = ref<HTMLElement | null>(null)

function scrollToCv() {
  const el = document.getElementById('bottomSection')
  if (!el) return

  // hitung offset agar tidak ketutup navbar
  const navH = navRef.value?.offsetHeight ?? 80
  const rect = el.getBoundingClientRect()
  const y = rect.top + window.scrollY - navH - 8

  window.scrollTo({ top: y, behavior: 'smooth' })

  // fokuskan input setelah animasi scroll (sedikit delay)
  setTimeout(() => el.focus?.(), 500)
}
</script>

<style scoped>
/* Optional: kecilkan bayangan saat user scroll (neo-brutalis feel tetap) */
:host {
  /* no-op: scope anchor */
}
</style>
