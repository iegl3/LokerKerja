<template>
  <div v-if="modalOpen" id="mobile-modal" class="fixed inset-0 z-[1000] md:hidden">
    <div class="absolute inset-0 bg-black/40" @click="closeModal" aria-hidden="true"></div>
    <section role="dialog" aria-modal="true" class="relative mx-auto my-8 w-[92%] max-w-lg bg-white border-4 border-neutral-900 rounded-2xl shadow-[12px_12px_0_0_#111]">
      <header class="flex items-center gap-3 p-4 border-b-4 border-neutral-900 bg-purple-200">
        <svg class="w-6 h-6">
          <use :href="modalTab==='cv' ? '#cv-doc' : '#briefcase'"/>
        </svg>
        <h3 class="font-black text-lg">{{ modalTab === 'cv' ? 'CV Analysis' : 'Job Matches' }}</h3>
        <button
            type="button"
            class="ml-auto bg-white text-neutral-900 px-3 py-1 rounded-xl font-extrabold border-4 border-neutral-900 shadow-[8px_8px_0_0_#111] active:translate-x-1 active:translate-y-1 active:shadow-[4px_4px_0_0_#111]"
            @click="closeModal"
        >
          Close
        </button>
      </header>

      <div class="p-4 max-h-[70vh] overflow-auto">
        <div v-if="modalTab==='cv'">
          <div class="grid gap-3">
            <div class="card"><div class="label">Name</div><div class="value">{{ result?.profile?.name ?? '—' }}</div></div>
            <div class="card"><div class="label">Skills Found</div><div class="value">{{ (result?.profile?.skills?.length ?? 0) }} skills</div></div>
            <div class="card"><div class="label">Experience</div><div class="value">{{ (result?.profile?.experience?.length ?? 0) }} roles</div></div>
            <div class="card"><div class="label">Total Duration</div><div class="value">{{ result?.profile?.total_duration ?? '—' }}</div></div>
            <div class="card"><div class="label">Education</div><div class="value">{{ (result?.profile?.education?.length ?? 0) }} entries</div></div>
            <div class="card"><div class="label">Processing Time</div><div class="value">{{ result?.meta?.total_ms ?? '—' }}</div></div>
          </div>
        </div>
        <div v-else>
          <ul class="grid gap-3">
            <li v-for="job in matches" :key="job.id" class="bg-white border-4 border-neutral-900 rounded-2xl p-4 shadow-[8px_8px_0_0_#111]">
              <div class="flex items-start gap-3">
                <svg class="w-6 h-6 text-neutral-900"><use href="#briefcase"/></svg>
                <div class="flex-1">
                  <div class="font-extrabold leading-snug">{{ job.title }}</div>
                  <div class="text-sm text-neutral-700">{{ job.company }} <span v-if="job.location">• {{ job.location }}</span></div>
                </div>
                <div class="nb-chip bg-acc2" v-if="job.matchPct != null">{{ job.matchPct }}%</div>
              </div>
              <div class="mt-2">
                <a v-if="job.url" :href="job.url" target="_blank" rel="noopener" class="font-extrabold text-green-600 hover:text-green-700 underline underline-offset-2 decoration-4 decoration-green-300">View →</a>
              </div>
            </li>
          </ul>
        </div>
      </div>

      <footer class="p-3 border-t-4 border-neutral-900 flex gap-2">
        <button
            type="button"
            :class="[
            'px-4 py-2 rounded-xl font-extrabold border-4 border-neutral-900 shadow-[8px_8px_0_0_#111] active:translate-x-1 active:translate-y-1 active:shadow-[4px_4px_0_0_#111] w-full inline-flex justify-center items-center gap-2',
            modalTab==='cv' ? 'bg-blue-200 hover:bg-blue-300 text-neutral-900' : 'bg-white text-neutral-900'
          ]"
            @click="openModal('cv')"
        >
          <svg class="w-5 h-5"><use href="#cv-doc"/></svg><span>CV</span>
        </button>
        <button
            v-if="matches.length"
            type="button"
            :class="[
            'px-4 py-2 rounded-xl font-extrabold border-4 border-neutral-900 shadow-[8px_8px_0_0_#111] active:translate-x-1 active:translate-y-1 active:shadow-[4px_4px_0_0_#111] w-full inline-flex justify-center items-center gap-2',
            modalTab==='jobs' ? 'bg-green-200 hover:bg-green-300 text-neutral-900' : 'bg-white text-neutral-900'
          ]"
            @click="openModal('jobs')"
        >
          <svg class="w-5 h-5"><use href="#briefcase"/></svg><span>Jobs</span>
        </button>
      </footer>
    </section>
  </div>
</template>

<script setup lang="ts">
import { useCvFlow } from '~/composables/useCvFlow'
const { modalOpen, modalTab, result, matches, openModal, closeModal } = useCvFlow()
</script>

<style scoped>
.card{ background:#fff; border:4px solid #111; border-radius:12px; padding:.75rem; box-shadow:6px 6px 0 0 #111; }
.card .label{ font-size:.7rem; font-weight:900; letter-spacing:.06em; text-transform:uppercase; color:#525252; }
.card .value{ margin-top:.25rem; font-weight:800; }
.nb-chip{ display:inline-flex; align-items:center; gap:.5rem; padding:.4rem .7rem; border-radius:12px; font-weight:700; border:3px solid #111; box-shadow:6px 6px 0 0 #111; }
.bg-acc2{ background:#2EC4B6; }
</style>
