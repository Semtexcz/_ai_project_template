<script setup lang="ts">
import { onMounted } from 'vue'

import { useSystemInfo } from '../composables/useSystemInfo'

const systemInfo = useSystemInfo()

onMounted(() => {
  void systemInfo.load()
})
</script>

<template>
  <section aria-labelledby="system-info-title" class="system-info">
    <p class="eyebrow">fullstack-local</p>
    <h1 id="system-info-title">{{ systemInfo.data.value?.name || 'System information' }}</h1>

    <p v-if="systemInfo.loading.value" aria-live="polite" class="status">
      Loading system information...
    </p>

    <p v-else-if="systemInfo.error.value" role="alert" class="error">
      {{ systemInfo.error.value }}
    </p>

    <dl v-else-if="systemInfo.data.value" class="details">
      <div>
        <dt>Version</dt>
        <dd>{{ systemInfo.data.value.version }}</dd>
      </div>
      <div>
        <dt>Environment</dt>
        <dd>{{ systemInfo.data.value.environment }}</dd>
      </div>
      <div>
        <dt>Next step</dt>
        <dd>{{ systemInfo.data.value.next_step }}</dd>
      </div>
    </dl>
  </section>
</template>

<style scoped>
.system-info {
  width: min(100%, 44rem);
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

.status,
.error {
  margin: 1rem 0 0;
  color: #46546a;
  font-size: 1rem;
  line-height: 1.6;
}

.error {
  color: #a43b3b;
  font-weight: 700;
}

.details {
  display: grid;
  gap: 1rem;
  margin: 1.5rem 0 0;
}

.details div {
  display: grid;
  grid-template-columns: minmax(8rem, 12rem) 1fr;
  gap: 1rem;
  align-items: baseline;
  padding-top: 1rem;
  border-top: 1px solid #e8edf4;
}

dt {
  color: #46546a;
  font-size: 0.875rem;
  font-weight: 700;
}

dd {
  margin: 0;
  color: #172033;
}

@media (max-width: 38rem) {
  .details div {
    grid-template-columns: 1fr;
    gap: 0.25rem;
  }
}
</style>
