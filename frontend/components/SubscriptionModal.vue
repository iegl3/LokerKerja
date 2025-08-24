<template>
  <div v-if="subscriptionOpen" class="fixed inset-0 z-[1200]">
    <div class="absolute inset-0 bg-black/40" @click="closeSubscription" aria-hidden="true"></div>
    <section role="dialog" aria-modal="true" class="relative mx-auto my-8 w-[92%] max-w-2xl bg-white border-4 border-neutral-900 rounded-2xl shadow-[12px_12px_0_0_#111]">
      <header class="flex items-center gap-3 p-4 border-b-4 border-neutral-900 bg-purple-200">
        <svg class="w-6 h-6" viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <path d="M4 6h16v12H4z" stroke="currentColor" stroke-width="2"/><path d="M4 6l8 6 8-6" stroke="currentColor" stroke-width="2" />
        </svg>
        <h3 class="font-black text-lg">Job Alerts (Email)</h3>
        <button type="button" class="ml-auto bg-white text-neutral-900 px-3 py-1 rounded-xl font-extrabold border-4 border-neutral-900 shadow-[8px_8px_0_0_#111] active:translate-x-1 active:translate-y-1 active:shadow-[4px_4px_0_0_#111]" @click="closeSubscription">Close</button>
      </header>

      <div class="p-4">
        <!-- Step: Offer Email -->
        <div v-if="subStep==='offer'">
          <p class="mb-3 font-semibold">Get fresh jobs like these in your inbox.</p>
          <label class="block mb-4">
            <span class="text-xs font-black uppercase mb-1 block">Email</span>
            <input v-model.trim="subEmail" type="email" placeholder="you@example.com" class="w-full bg-white border-4 border-neutral-900 rounded-xl px-3 py-2 shadow-[6px_6px_0_0_#111]" />
          </label>
          <div class="flex justify-end gap-2">
            <button type="button" class="bg-white text-neutral-900 px-4 py-2 rounded-xl font-extrabold border-4 border-neutral-900 shadow-[8px_8px_0_0_#111] active:translate-x-1 active:translate-y-1 active:shadow-[4px_4px_0_0_#111]" @click="closeSubscription">Not now</button>
            <button type="button" class="bg-blue-200 hover:bg-blue-300 text-neutral-900 px-4 py-2 rounded-xl font-extrabold border-4 border-neutral-900 shadow-[8px_8px_0_0_#111] active:translate-x-1 active:translate-y-1 active:shadow-[4px_4px_0_0_#111]" @click="goReview" :disabled="!subEmail">Continue</button>
          </div>
        </div>

        <!-- Step: Review -->
        <div v-else-if="subStep==='review'">
          <div class="grid gap-3 md:grid-cols-2 mb-4">
            <div class="card"><div class="label">Email</div><div class="value break-all">{{ subEmail }}</div></div>
            <div class="card"><div class="label">Position</div><div class="value">{{ subPosition || inferredTitle || '—' }}</div></div>
            <div class="card"><div class="label">Location</div><div class="value">{{ subLocationParam }}</div></div>
            <div class="card"><div class="label">Sites</div><div class="value">{{ subSites.join(', ') || '—' }}</div></div>
            <div class="card"><div class="label">Language</div><div class="value uppercase">{{ subLanguage }}</div></div>
            <div class="card"><div class="label">Top Matches</div><div class="value">{{ subTopMatches }}</div></div>
          </div>
          <div class="flex justify-end gap-2">
            <button type="button" class="bg-white text-neutral-900 px-4 py-2 rounded-xl font-extrabold border-4 border-neutral-900 shadow-[8px_8px_0_0_#111] active:translate-x-1 active:translate-y-1 active:shadow-[4px_4px_0_0_#111]" @click="subStep='edit'">Edit</button>
            <button type="button" :disabled="subSubmitting || !subEmail" class="bg-green-200 hover:bg-green-300 disabled:opacity-60 text-neutral-900 px-4 py-2 rounded-xl font-extrabold border-4 border-neutral-900 shadow-[8px_8px_0_0_#111] active:translate-x-1 active:translate-y-1 active:shadow-[4px_4px_0_0_#111]" @click="confirmSubscription">
              <span class="inline-flex items-center gap-2">
                <svg v-if="subSubmitting" class="w-5 h-5 animate-spin" viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="9" stroke="currentColor" stroke-width="3" opacity=".25"/><path d="M21 12a9 9 0 0 1-9 9" stroke="currentColor" stroke-width="3"/></svg>
                Confirm
              </span>
            </button>
          </div>
          <p v-if="subError" class="mt-2 text-red-600 font-bold">Error: {{ subError }}</p>
        </div>

        <!-- Step: Edit -->
        <div v-else class="grid gap-4 md:grid-cols-2">
          <label class="block md:col-span-2">
            <div class="text-xs font-black uppercase mb-1">Position (Final Role)</div>
            <input v-model.trim="subPosition" placeholder="e.g., Frontend Engineer" class="w-full bg-white border-4 border-neutral-900 rounded-xl px-3 py-2 shadow-[6px_6px_0_0_#111]" />
          </label>

          <label class="block">
            <div class="text-xs font-black uppercase mb-1">Seniority</div>
            <select v-model="subSeniority" class="w-full bg-white border-4 border-neutral-900 rounded-xl px-3 py-2 shadow-[6px_6px_0_0_#111]">
              <option value="intern">Intern</option><option value="junior">Junior</option><option value="mid">Mid</option><option value="senior">Senior</option><option value="lead">Lead</option>
            </select>
          </label>
          <label class="block">
            <div class="text-xs font-black uppercase mb-1">Frequency</div>
            <select v-model="subFrequency" class="w-full bg-white border-4 border-neutral-900 rounded-xl px-3 py-2 shadow-[6px_6px_0_0_#111]">
              <option value="daily">Daily</option><option value="weekly">Weekly</option><option value="monthly">Monthly</option>
            </select>
          </label>

          <label class="block">
            <div class="text-xs font-black uppercase mb-1">Top N</div>
            <input v-model.number="subTopN" type="number" min="1" max="50" class="w-full bg-white border-4 border-neutral-900 rounded-xl px-3 py-2 shadow-[6px_6px_0_0_#111]"/>
          </label>
          <label class="block">
            <div class="text-xs font-black uppercase mb-1">Alert threshold</div>
            <input v-model.number="subAlertThreshold" type="number" step="0.05" min="0" max="1" class="w-full bg-white border-4 border-neutral-900 rounded-xl px-3 py-2 shadow-[6px_6px_0_0_#111]"/>
          </label>

          <div class="md:col-span-2 flex items-center gap-3">
            <input id="subMatch" type="checkbox" v-model="subEnableMatching" class="accent-black scale-125">
            <label for="subMatch" class="font-bold">Enable matching</label>
            <input id="subScam" type="checkbox" v-model="subIncludeScam" class="accent-black scale-125 ml-5">
            <label for="subScam" class="font-bold">Enable scam check</label>
          </div>

          <label class="block md:col-span-2">
            <div class="text-xs font-black uppercase mb-1">Must-have skills (comma separated)</div>
            <input v-model.trim="subMustSkills" class="w-full bg-white border-4 border-neutral-900 rounded-xl px-3 py-2 shadow-[6px_6px_0_0_#111]" placeholder="e.g., React, TypeScript"/>
          </label>
          <label class="block md:col-span-2">
            <div class="text-xs font-black uppercase mb-1">Nice-to-have skills (comma separated)</div>
            <input v-model.trim="subNiceSkills" class="w-full bg-white border-4 border-neutral-900 rounded-xl px-3 py-2 shadow-[6px_6px_0_0_#111]" placeholder="e.g., Vue, GraphQL"/>
          </label>
          <label class="block md:col-span-2">
            <div class="text-xs font-black uppercase mb-1">Exclude keywords (comma separated)</div>
            <input v-model.trim="subExcludeKeywords" class="w-full bg-white border-4 border-neutral-900 rounded-xl px-3 py-2 shadow-[6px_6px_0_0_#111]" placeholder="e.g., Senior, Manager"/>
          </label>
          <label class="block md:col-span-2">
            <div class="text-xs font-black uppercase mb-1">Exclude companies (comma separated)</div>
            <input v-model.trim="subExcludeCompanies" class="w-full bg-white border-4 border-neutral-900 rounded-xl px-3 py-2 shadow-[6px_6px_0_0_#111]" placeholder="e.g., Company A, Company B"/>
          </label>

          <div class="md:col-span-2">
            <div class="text-xs font-black uppercase mb-2">Job types</div>
            <div class="flex flex-wrap gap-2">
              <label v-for="jt in ['fulltime','parttime','contract','internship']" :key="jt" class="inline-flex items-center gap-2 bg-white px-3 py-2 rounded-xl border-4 border-neutral-900 shadow-[6px_6px_0_0_#111] cursor-pointer">
                <input type="checkbox" :value="jt" v-model="subJobTypes" class="accent-black"/><span class="font-bold capitalize">{{ jt }}</span>
              </label>
            </div>
          </div>

          <label class="block">
            <div class="text-xs font-black uppercase mb-1">Remote type</div>
            <select v-model="subRemoteType" class="w-full bg-white border-4 border-neutral-900 rounded-xl px-3 py-2 shadow-[6px_6px_0_0_#111]">
              <option value="onsite">Onsite</option><option value="hybrid">Hybrid</option><option value="remote">Remote</option>
            </select>
          </label>
          <label class="block">
            <div class="text-xs font-black uppercase mb-1">Min salary</div>
            <input v-model.number="subSalaryMin" type="number" min="0" class="w-full bg-white border-4 border-neutral-900 rounded-xl px-3 py-2 shadow-[6px_6px_0_0_#111]"/>
          </label>
          <label class="block">
            <div class="text-xs font-black uppercase mb-1">Currency</div>
            <select v-model="subSalaryCurrency" class="w-full bg-white border-4 border-neutral-900 rounded-xl px-3 py-2 shadow-[6px_6px_0_0_#111]">
              <option value="IDR">IDR</option><option value="USD">USD</option><option value="SGD">SGD</option><option value="EUR">EUR</option>
            </select>
          </label>

          <div class="flex justify-end gap-2 md:col-span-2 mt-2">
            <button type="button" class="bg-white text-neutral-900 px-4 py-2 rounded-xl font-extrabold border-4 border-neutral-900 shadow-[8px_8px_0_0_#111] active:translate-x-1 active:translate-y-1 active:shadow-[4px_4px_0_0_#111]" @click="subStep='review'">Back</button>
            <button type="button" class="bg-gray-200 hover:bg-gray-300 text-neutral-900 px-4 py-2 rounded-xl font-extrabold border-4 border-neutral-900 shadow-[8px_8px_0_0_#111] active:translate-x-1 active:translate-y-1 active:shadow-[4px_4px_0_0_#111]" @click="subStep='review'">Save</button>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { useCvFlow } from '~/composables/useCvFlow'
const {
  subscriptionOpen, closeSubscription, subStep, goReview, confirmSubscription,
  subEmail, subSubmitting, subError,
  inferredTitle, subPosition, subSeniority, subFrequency, subTopN, subAlertThreshold,
  subMustSkills, subNiceSkills, subExcludeKeywords, subExcludeCompanies,
  subJobTypes, subRemoteType, subSalaryMin, subSalaryCurrency,
  subLocation, subCustomLocation, subSites, subLanguage, subTopMatches, subResultsWanted,
  subEnableMatching, subIncludeScam, subLocationParam
} = useCvFlow()
</script>

<style scoped>
.card{ background:#fff; border:4px solid #111; border-radius:12px; padding:.75rem; box-shadow:6px 6px 0 0 #111; }
.card .label{ font-size:.7rem; font-weight:900; letter-spacing:.06em; text-transform:uppercase; color:#525252; }
.card .value{ margin-top:.25rem; font-weight:800; }
</style>

