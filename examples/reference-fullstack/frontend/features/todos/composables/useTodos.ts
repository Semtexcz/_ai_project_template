import { ref } from 'vue'

export interface Todo {
  id: string
  title: string
  completed: boolean
}

export function useTodos() {
  const todos = ref<Todo[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function refresh() {
    loading.value = true
    error.value = null
    try {
      todos.value = await $fetch<Todo[]>('/api/todos')
    } catch {
      error.value = 'Unable to load todos'
    } finally {
      loading.value = false
    }
  }

  return { todos, loading, error, refresh }
}
