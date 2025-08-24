<template>
  <section class="min-h-screen jokowi flex flex-col md:flex-row">
    <div class="relative flex-1 flex w-full items-center justify-center text-neutral-900 p-6">
      <div class="relative max-w-lg">
        <div class="relative space-y-5">
          <h1 class="text-4xl md:text-6xl font-black">Loker Kerja</h1>
          <p class="text-lg md:text-xl">Find your perfect job with AI-powered CV matching, quick and easy with no hassle!</p>
          <p class="text-lg md:text-xl">Upload your CV in one step, and let AI do the rest. Your privacy's matter</p>
          <div class="flex flex-wrap gap-3 pt-1">
            <span class="nb-chip bg-acc1">ATS Friendly</span>
            <span class="nb-chip bg-acc2">AI Match</span>
            <span class="nb-chip bg-acc3">Privacy First</span>
          </div>
        </div>
      </div>
    </div>

    <div class="flex-1 flex items-center justify-center p-6">
      <figure class="nb-photo w-full max-w-md">
        <img class="w-full h-auto block rounded-xl" alt="Illustration placeholder" src="/employee.jpg" />
        <figcaption class="sr-only">Placeholder image with neo-brutalist frame</figcaption>
      </figure>
    </div>
  </section>
</template>

<style scoped>
.jokowi{
  background-size:100px 100px;
  background-image:
      linear-gradient(to right, rgba(0,0,0,.18) 1px, transparent 1px),
      linear-gradient(to bottom, rgba(0,0,0,.18) 1px, transparent 1px);
}
.nb-photo{ background:#fff; border:4px solid #111; border-radius:16px; box-shadow:12px 12px 0 0 #111; overflow:hidden; }
.nb-chip{ display:inline-flex; align-items:center; gap:.5rem; padding:.4rem .7rem; border-radius:12px; font-weight:700; border:3px solid #111; box-shadow:6px 6px 0 0 #111; }
.bg-acc1{ background:#FFD803; } .bg-acc2{ background:#2EC4B6; } .bg-acc3{ background:#FF6B6B; }
</style>

