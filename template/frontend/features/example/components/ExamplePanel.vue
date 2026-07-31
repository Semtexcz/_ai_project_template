<script setup lang="ts">
import { useExample } from '../composables/useExample'

const { state, refresh } = useExample()
</script>

<template>
  <section aria-labelledby="example-title" class="max-w-xl">
    <h1 id="example-title">{{ state.title }}</h1>
    <p v-if="state.status === 'success'">{{ state.message }}</p>
    <p v-else-if="state.status === 'error'" role="alert">{{ state.error }}</p>
    <p v-else-if="state.status === 'empty'">No example message yet.</p>
    <p v-else>Loading...</p>
    <button type="button" @click="refresh">Refresh</button>
  </section>
</template>
