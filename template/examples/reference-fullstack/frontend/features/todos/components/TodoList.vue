<script setup lang="ts">
import { onMounted } from 'vue'
import EmptyState from '../../../shared/ui/EmptyState.vue'
import { useTodos } from '../composables/useTodos'

const { todos, loading, error, refresh } = useTodos()

onMounted(refresh)
</script>

<template>
  <section aria-labelledby="todos-title">
    <h1 id="todos-title">Todos</h1>
    <p v-if="loading">Loading...</p>
    <p v-else-if="error" role="alert">{{ error }}</p>
    <EmptyState v-else-if="todos.length === 0" message="No todos yet." />
    <ul v-else>
      <li v-for="todo in todos" :key="todo.id">{{ todo.title }}</li>
    </ul>
  </section>
</template>
