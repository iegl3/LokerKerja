<template>
  <div v-if="optionsOpen" class="fixed inset-0 z-[1100]">
    <div class="absolute inset-0 bg-black/40" @click="closeOptions" aria-hidden="true"></div>

    <section role="dialog" aria-modal="true"
             class="relative mx-auto my-8 w-[92%] max-w-2xl bg-white border-4 border-neutral-900 rounded-2xl shadow-[12px_12px_0_0_#111]">
      <header class="flex items-center gap-3 p-4 border-b-4 border-neutral-900 bg-purple-200">
        <svg class="w-6 h-6" viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <path d="M12 15.5a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7Z" stroke="currentColor" stroke-width="2" />
          <path d="M19 12a7 7 0 0 0-.1-1l2-1.2-2-3.4-2.3 1a7 7 0 0 0-1.7-1l-.3-2.5h-4l-.3 2.5c-.6-.2-1.2-.5-1.7-1l-2.3-1-2 3.4 2 1.2A7 7 0 0 0 5 12c0 .3 0 .7.1 1l-2 1.2 2 3.4 2.3-1c.5.5 1.1.8 1.7 1l.3 2.5h4l.3-2.5c.6-.2 1.2-.5 1.7-1l2.3 1 2-3.4-2-1.2c.1-.3.1-.7.1-1Z" stroke="currentColor" stroke-width="2" stroke-linejoin="round" />
        </svg>
        <h3 class="font-black text-lg">Job Search Options</h3>
        <button type="button" class="ml-auto bg-white text-neutral-900 px-3 py-1 rounded-xl font-extrabold border-4 border-neutral-900 shadow-[8px_8px_0_0_#111] active:translate-x-1 active:translate-y-1 active:shadow-[4px_4px_0_0_#111]" @click="closeOptions">Close</button>
      </header>

      <div class="p-4 grid gap-4 md:grid-cols-2">
        <!-- Location -->
        <label class="block md:col-span-2">
          <div class="text-xs font-black uppercase mb-1">Location</div>
          <select v-model="optLocation" class="w-full bg-white border-4 border-neutral-900 rounded-xl px-3 py-2 shadow-[6px_6px_0_0_#111]">
            <optgroup label="🇮🇩 Indonesia">
              <option value="Indonesia">Indonesia (All cities)</option>
              <option value="Jakarta, Indonesia">Jakarta</option>
              <option value="Surabaya, Indonesia">Surabaya</option>
              <option value="Bandung, Indonesia">Bandung</option>
              <option value="Medan, Indonesia">Medan</option>
              <option value="Yogyakarta, Indonesia">Yogyakarta</option>
              <option value="Semarang, Indonesia">Semarang</option>
              <option value="Bali, Indonesia">Bali</option>
            </optgroup>
            <optgroup label="Remote">
              <option value="Remote">Remote (Worldwide)</option>
              <option value="Remote, Indonesia">Remote (Indonesia)</option>
              <option value="Remote, Asia">Remote (Asia)</option>
            </optgroup>
            <optgroup label="🌏 Asia Pacific">
              <option value="Singapore">Singapore</option>
              <option value="Kuala Lumpur, Malaysia">Malaysia</option>
              <option value="Bangkok, Thailand">Thailand</option>
              <option value="Manila, Philippines">Philippines</option>
              <option value="Ho Chi Minh City, Vietnam">Vietnam</option>
              <option value="Hong Kong">Hong Kong</option>
              <option value="Tokyo, Japan">Japan</option>
              <option value="Seoul, South Korea">South Korea</option>
              <option value="Sydney, Australia">Australia</option>
              <option value="Auckland, New Zealand">New Zealand</option>
            </optgroup>
            <optgroup label="🇺🇸 North America">
              <option value="United States">USA (All states)</option>
              <option value="San Francisco, CA">San Francisco, CA</option>
              <option value="New York, NY">New York, NY</option>
              <option value="Seattle, WA">Seattle, WA</option>
              <option value="Austin, TX">Austin, TX</option>
              <option value="Boston, MA">Boston, MA</option>
              <option value="Chicago, IL">Chicago, IL</option>
              <option value="Los Angeles, CA">Los Angeles, CA</option>
              <option value="Canada">Canada (All provinces)</option>
              <option value="Toronto, Canada">Toronto, Canada</option>
              <option value="Vancouver, Canada">Vancouver, Canada</option>
            </optgroup>
            <optgroup label="🇪🇺 Europe">
              <option value="United Kingdom">United Kingdom</option>
              <option value="London, UK">London, UK</option>
              <option value="Germany">Germany</option>
              <option value="Berlin, Germany">Berlin, Germany</option>
              <option value="Munich, Germany">Munich, Germany</option>
              <option value="Netherlands">Netherlands</option>
              <option value="Amsterdam, Netherlands">Amsterdam</option>
              <option value="France">France</option>
              <option value="Paris, France">Paris, France</option>
              <option value="Switzerland">Switzerland</option>
              <option value="Zurich, Switzerland">Zurich</option>
              <option value="Sweden">Sweden</option>
              <option value="Stockholm, Sweden">Stockholm</option>
              <option value="Denmark">Denmark</option>
              <option value="Copenhagen, Denmark">Copenhagen</option>
            </optgroup>
            <optgroup label="🕌 Middle East">
              <option value="Dubai, UAE">Dubai, UAE</option>
              <option value="Abu Dhabi, UAE">Abu Dhabi, UAE</option>
              <option value="Riyadh, Saudi Arabia">Saudi Arabia</option>
              <option value="Doha, Qatar">Qatar</option>
              <option value="Kuwait City, Kuwait">Kuwait</option>
            </optgroup>
            <optgroup label="🌍 Other Popular">
              <option value="India">India</option>
              <option value="Bangalore, India">Bangalore, India</option>
              <option value="Mumbai, India">Mumbai, India</option>
              <option value="Brazil">Brazil</option>
              <option value="São Paulo, Brazil">São Paulo, Brazil</option>
              <option value="Mexico">Mexico</option>
              <option value="Mexico City, Mexico">Mexico City</option>
              <option value="South Africa">South Africa</option>
              <option value="Cape Town, South Africa">Cape Town</option>
            </optgroup>
            <optgroup label="✏️ Custom"><option value="custom">Enter custom location...</option></optgroup>
          </select>
          <div v-if="optLocation === 'custom'" class="mt-2">
            <input v-model.trim="optCustomLocation" class="w-full bg-white border-4 border-neutral-900 rounded-xl px-3 py-2 shadow-[6px_6px_0_0_#111]" placeholder="e.g., Oslo, Norway" />
            <div class="text-xs text-neutral-600 mt-1">Tip: format “City, Country”.</div>
          </div>
        </label>

        <label class="block">
          <div class="text-xs font-black uppercase mb-1">Results wanted</div>
          <input v-model.number="optResultsWanted" type="number" min="1" max="100" class="w-full bg-white border-4 border-neutral-900 rounded-xl px-3 py-2 shadow-[6px_6px_0_0_#111]" />
        </label>
        <label class="block">
          <div class="text-xs font-black uppercase mb-1">Language</div>
          <select v-model="optLanguage" class="w-full bg-white border-4 border-neutral-900 rounded-xl px-3 py-2 shadow-[6px_6px_0_0_#111]">
            <option value="en">English</option><option value="id">Bahasa Indonesia</option>
          </select>
        </label>
        <label class="block">
          <div class="text-xs font-black uppercase mb-1">Top matches</div>
          <input v-model.number="optTopMatches" type="number" min="1" max="50" class="w-full bg-white border-4 border-neutral-900 rounded-xl px-3 py-2 shadow-[6px_6px_0_0_#111]" />
        </label>

        <div class="md:col-span-2">
          <div class="text-xs font-black uppercase mb-2">Sites</div>
          <div class="flex flex-wrap gap-2">
            <label v-for="site in allSitesList" :key="site" class="inline-flex items-center gap-2 bg-white px-3 py-2 rounded-xl border-4 border-neutral-900 shadow-[6px_6px_0_0_#111] cursor-pointer select-none">
              <input type="checkbox" :value="site" v-model="optSites" class="accent-black" />
              <span class="font-bold capitalize">{{ site }}</span>
            </label>
          </div>
        </div>

        <div class="flex items-center gap-3">
          <input id="toggleMatching" type="checkbox" v-model="optEnableMatching" class="accent-black scale-125" />
          <label for="toggleMatching" class="font-bold">Enable matching</label>
        </div>
        <div class="flex items-center gap-3">
          <input id="toggleScam" type="checkbox" v-model="optIncludeScam" class="accent-black scale-125" />
          <label for="toggleScam" class="font-bold">Include scam check</label>
        </div>
      </div>

      <footer class="p-4 border-t-4 border-neutral-900 flex gap-2 justify-end">
        <button type="button" class="bg-white text-neutral-900 px-4 py-2 rounded-xl font-extrabold border-4 border-neutral-900 shadow-[8px_8px_0_0_#111] active:translate-x-1 active:translate-y-1 active:shadow-[4px_4px_0_0_#111]" @click="closeOptions">Cancel</button>
        <button type="button" class="bg-gray-200 hover:bg-gray-300 text-neutral-900 px-4 py-2 rounded-xl font-extrabold border-4 border-neutral-900 shadow-[8px_8px_0_0_#111] active:translate-x-1 active:translate-y-1 active:shadow-[4px_4px_0_0_#111]" @click="applyOptions">Apply</button>
      </footer>
    </section>
  </div>
</template>

<script setup lang="ts">
import { allSites, useCvFlow } from '~/composables/useCvFlow'
const {
  optionsOpen, closeOptions, applyOptions,
  optLocation, optCustomLocation, optResultsWanted, optLanguage, optTopMatches,
  optSites, optEnableMatching, optIncludeScam
} = useCvFlow()
const allSitesList = allSites
</script>

