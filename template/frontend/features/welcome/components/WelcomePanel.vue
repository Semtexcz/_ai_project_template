<script setup lang="ts">
import { computed } from 'vue'

import { normalizeWelcomeContent } from '../composables/useWelcomeContent'
import type { WelcomeContent } from '../types/welcome'

const props = defineProps<{
  content: WelcomeContent
}>()

const normalized = computed(() => normalizeWelcomeContent(props.content))
</script>

<template>
  <section aria-labelledby="welcome-title" class="welcome-panel">
    <p class="eyebrow">frontend-shared</p>
    <h1 id="welcome-title">{{ normalized.projectName }}</h1>
    <p class="summary">{{ normalized.description }}</p>
    <a class="next-link" :href="normalized.nextStepHref">
      {{ normalized.nextStepLabel }}
    </a>
  </section>
</template>

<style scoped>
.welcome-panel {
  width: min(100%, 42rem);
  padding: 2rem;
  border: 1px solid #d8dee8;
  border-radius: 8px;
  background: #ffffff;
  box-shadow: 0 16px 40px rgb(23 32 51 / 0.08);
}

.eyebrow {
  margin: 0 0 0.75rem;
  color: #4f6f52;
  font-size: 0.875rem;
  font-weight: 700;
  letter-spacing: 0;
  text-transform: uppercase;
}

h1 {
  margin: 0;
  color: #172033;
  font-size: clamp(2rem, 4vw, 3.5rem);
  line-height: 1.05;
  letter-spacing: 0;
}

.summary {
  margin: 1rem 0 1.5rem;
  color: #46546a;
  font-size: 1.075rem;
  line-height: 1.6;
}

.next-link {
  color: #1d5f8a;
  font-weight: 700;
  text-underline-offset: 0.2em;
}

.next-link:focus-visible {
  outline: 3px solid #f0b84f;
  outline-offset: 4px;
}
</style>
