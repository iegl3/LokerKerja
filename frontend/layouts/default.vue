<template>
  <div class="min-h-screen flex flex-col bg-purple-50 grid-pattern">

    <NavBar />
    <main class="flex-1 p-8">
      <slot />
    </main>
    <footer class="p-4 border-t-2 border text-sm bg-purple-400">© 2025 - SuikaStudio. LankZ & Hank</footer>
  </div>
</template>

<style>




</style>