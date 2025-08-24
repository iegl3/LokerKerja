<template>
  <section class="py-10 md:py-16" id="bottomSection">
    <div class="max-w-4xl mx-auto px-6">
      <div class="p-6 md:p-8 bg-purple-50 border-4 border-neutral-900 rounded-2xl shadow-[12px_12px_0_0_#111]">
        <header class="flex items-start gap-3 mb-6">
          <svg class="w-7 h-7 text-neutral-900"><use href="#cv-doc"/></svg>
          <div>
            <h2 class="text-2xl md:text-3xl font-black leading-tight">Upload your CV</h2>
            <p class="text-neutral-600">PDF / PNG / JPG / WebP — max 10MB. We’ll analyze it with AI.</p>
          </div>
        </header>

        <form class="space-y-5" enctype="multipart/form-data" @submit.prevent="onSubmit">
          <label
              for="cvFile"
              class="group block bg-white border-4 border-neutral-900 rounded-2xl p-6 md:p-8 shadow-[8px_8px_0_0_#111] cursor-pointer transition hover:bg-purple-50 hover:shadow-[12px_12px_0_0_#111]"
          >
            <div class="flex items-center gap-4">
              <div class="shrink-0 grid place-items-center w-14 h-14 rounded-xl bg-purple-100 border-4 border-neutral-900 shadow-[6px_6px_0_0_#111]">
                <svg class="w-7 h-7 text-neutral-900"><use href="#upload"/></svg>
              </div>
              <div class="flex-1">
                <div class="font-extrabold text-lg">Drop your CV here or click to choose</div>
                <div class="text-sm text-neutral-600">Supports .pdf, .png, .jpg, .jpeg, .webp</div>
                <div v-if="fileName" class="mt-1 text-sm font-semibold text-purple-600">Selected: {{ fileName }}</div>
              </div>
            </div>
            <input
                id="cvFile"
                ref="fileInputRef"
                name="file"
                type="file"
                accept=".pdf,.png,.jpg,.jpeg,.webp"
                class="sr-only"
                @change="onFileChange"
                required
            />
          </label>

          <div class="flex flex-wrap items-center gap-3">
            <button
                v-if="!result && !matches.length"
                type="submit"
                :disabled="loading"
                :class="[
                'group bg-white text-neutral-900 px-5 py-3 rounded-xl font-extrabold',
                'border-4 border-neutral-900 shadow-[8px_8px_0_0_#111]',
                'active:translate-x-1 active:translate-y-1 active:shadow-[4px_4px_0_0_#111]',
                'disabled:opacity-60',
                hasFile && !loading ? 'nb-blink-green' : ''
              ]"
            >
              <span class="inline-flex items-center gap-2">
                <svg class="w-5 h-5"><use href="#bolt-ai"/></svg>
                {{ loading ? 'Analyzing…' : 'Analyze my CV' }}
                <svg v-if="hasFile && !loading" class="w-5 h-5 nb-arrow-plain" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                  <path d="M12 4v14M5 13l7 7 7-7" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                </svg>
              </span>
            </button>

            <button
                v-if="hasFile && !loading && !result && !matches.length"
                type="button"
                @click="openOptions()"
                :class="[
                'bg-gray-200 hover:bg-gray-300 text-neutral-900 px-4 py-3 rounded-xl font-extrabold',
                'border-4 border-neutral-900 shadow-[8px_8px_0_0_#111]',
                'active:translate-x-1 active:translate-y-1 active:shadow-[4px_4px_0_0_#111]',
                'inline-flex items-center gap-2','nb-blink-gray'
              ]"
            >
              <svg class="w-5 h-5" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                <path d="M12 15.5a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7Z" stroke="currentColor" stroke-width="2"/>
                <path d="M19 12a7 7 0 0 0-.1-1l2-1.2-2-3.4-2.3 1a7 7 0 0 0-1.7-1l-.3-2.5h-4l-.3 2.5c-.6-.2-1.2-.5-1.7-1l-2.3-1-2 3.4 2 1.2A7 7 0 0 0 5 12c0 .3 0 .7.1 1l-2 1.2 2 3.4 2.3-1c.5.5 1.1.8 1.7 1l.3 2.5h4l.3-2.5c.6-.2 1.2-.5 1.7-1l2.3 1 2-3.4-2-1.2c.1-.3.1-.7.1-1Z" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/>
              </svg>
              <span>Options</span>
            </button>

            <button
                v-else-if="result || matches.length"
                type="button"
                @click="clearAll"
                class="bg-red-200 hover:bg-red-300 text-neutral-900 px-5 py-3 rounded-xl font-extrabold border-4 border-neutral-900 shadow-[8px_8px_0_0_#111] active:translate-x-1 active:translate-y-1 active:shadow-[4px_4px_0_0_#111]"
                title="Clear current analysis & matches"
            >
              Clear
            </button>
          </div>

          <div class="mt-2 min-h-[1.5rem]">
            <div v-if="loading" class="inline-flex items-center gap-2">
              <span class="inline-block w-5 h-5 rounded-full border-4 border-neutral-900 border-t-transparent animate-spin"></span>
              <span :class="{
                'text-purple-700 font-black text-base': /Analyzing/i.test(statusMsg),
                'text-blue-700 font-black text-base': /Infer/i.test(statusMsg),
                'text-green-700 font-black text-base': /Finding job/i.test(statusMsg)
              }">{{ statusMsg }}</span>
            </div>
            <div v-else class="text-sm text-neutral-700">{{ statusMsg }}</div>
          </div>

          <div v-if="(result || matches.length) && !loading" class="md:hidden mt-4 grid grid-cols-2 gap-3">
            <button
                type="button"
                class="bg-blue-200 hover:bg-blue-300 text-neutral-900 px-4 py-2 rounded-xl font-extrabold border-4 border-neutral-900 shadow-[8px_8px_0_0_#111] active:translate-x-1 active:translate-y-1 active:shadow-[4px_4px_0_0_#111] w-full inline-flex justify-center items-center gap-2"
                @click="openModal('cv')"
                aria-controls="mobile-modal"
            >
              <svg class="w-5 h-5"><use href="#cv-doc"/></svg>
              <span>CV Analysis</span>
            </button>
            <button
                v-if="matches.length"
                type="button"
                class="bg-green-200 hover:bg-green-300 text-neutral-900 px-4 py-2 rounded-xl font-extrabold border-4 border-neutral-900 shadow-[8px_8px_0_0_#111] active:translate-x-1 active:translate-y-1 active:shadow-[4px_4px_0_0_#111] w-full inline-flex justify-center items-center gap-2"
                @click="openModal('jobs')"
                aria-controls="mobile-modal"
            >
              <svg class="w-5 h-5"><use href="#briefcase"/></svg>
              <span>Job Matches</span>
            </button>
          </div>

          <div v-if="result" class="hidden md:block mt-5 bg-purple-100 border-4 border-neutral-900 rounded-2xl p-4 shadow-[8px_8px_0_0_#111]">
            <div class="grid gap-3 md:grid-cols-3">
              <div class="card"><div class="label">Name</div><div class="value">{{ result.profile?.name ?? '—' }}</div></div>
              <div class="card"><div class="label">Skills Found</div><div class="value">{{ (result.profile?.skills?.length ?? 0) }} skills</div></div>
              <div class="card"><div class="label">Experience</div><div class="value">{{ (result.profile?.experience?.length ?? 0) }} roles</div></div>
              <div class="card"><div class="label">Total Duration</div><div class="value">{{ result.profile?.total_duration ?? '—' }}</div></div>
              <div class="card"><div class="label">Education</div><div class="value">{{ (result.profile?.education?.length ?? 0) }} entries</div></div>
              <div class="card"><div class="label">Processing Time</div><div class="value">{{ result.meta?.total_ms ?? '—' }}</div></div>
            </div>
          </div>

          <div v-if="matches.length" class="hidden md:block mt-6">
            <h3 class="text-xl md:text-2xl font-black mb-3">Top Matches</h3>
            <ul class="grid gap-4 md:grid-cols-2">
              <li v-for="job in matches" :key="job.id" class="bg-white border-4 border-neutral-900 rounded-2xl p-4 shadow-[8px_8px_0_0_#111]">
                <div class="flex items-start gap-3">
                  <svg class="w-6 h-6 text-neutral-900"><use href="#briefcase"/></svg>
                  <div class="flex-1">
                    <div class="font-extrabold text-lg leading-snug">{{ job.title }}</div>
                    <div class="text-sm text-neutral-700">{{ job.company }} <span v-if="job.location">• {{ job.location }}</span></div>
                    <div class="text-sm mt-1" v-if="job.salary_text">{{ job.salary_text }}</div>
                  </div>
                  <div class="nb-chip bg-acc2" v-if="job.matchPct != null">{{ job.matchPct }}%</div>
                </div>
                <div class="mt-3">
                  <a v-if="job.url" :href="job.url" target="_blank" rel="noopener"
                     class="font-extrabold text-green-600 hover:text-green-700 underline underline-offset-2 decoration-4 decoration-green-300">
                    View →
                  </a>
                </div>
              </li>
            </ul>
          </div>
        </form>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { useCvFlow } from '~/composables/useCvFlow'
const {
  fileInputRef, fileName, hasFile,
  loading, statusMsg, result, matches,
  onFileChange, onSubmit, clearAll,
  openOptions, openModal
} = useCvFlow()
</script>

<style scoped>
.card{ background:#fff; border:4px solid #111; border-radius:12px; padding:.75rem; box-shadow:6px 6px 0 0 #111; }
.card .label{ font-size:.7rem; font-weight:900; letter-spacing:.06em; text-transform:uppercase; color:#525252; }
.card .value{ margin-top:.25rem; font-weight:800; }

@keyframes nb-bob-y { 0%,100%{transform:translateY(0)} 50%{transform:translateY(3px)} }
.nb-arrow-plain{ animation: nb-bob-y 1s ease-in-out infinite; filter:none; }

@keyframes nb-blink-green { 0%,100%{background-color:#ffffff} 50%{background-color:#bbf7d0} }
.nb-blink-green{ animation: nb-blink-green 1.1s ease-in-out infinite; }

@keyframes nb-blink-gray { 0%,100%{background-color:#e5e7eb} 50%{background-color:#ffffff} }
.nb-blink-gray{ animation: nb-blink-gray .85s ease-in-out infinite; }

@media (prefers-reduced-motion: reduce){
  .nb-arrow-plain,.nb-blink-green,.nb-blink-gray{ animation:none; }
}
</style>


