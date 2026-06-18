<script setup>
import { onMounted } from 'vue'
import { useAuthStore } from './stores/auth'
import LoginForm from './components/LoginForm.vue'
import GanttView from './components/GanttView.vue'

const auth = useAuthStore()
onMounted(auth.init)
</script>

<template>
  <v-app>
    <v-app-bar color="primary" density="comfortable" flat>
      <v-app-bar-title>Vue3 + DRF ガントチャート</v-app-bar-title>
      <template #append v-if="auth.user">
        <span class="text-body-2 mr-3">{{ auth.user.username }}</span>
        <v-btn variant="text" prepend-icon="mdi-logout" @click="auth.logout">ログアウト</v-btn>
      </template>
    </v-app-bar>

    <v-main>
      <div v-if="auth.initializing" class="loading-center">
        <v-progress-circular indeterminate color="primary" />
      </div>
      <LoginForm v-else-if="!auth.user" />
      <div v-else class="main-area">
        <GanttView />
      </div>
    </v-main>
  </v-app>
</template>

<style>
html, body, #app {
  height: 100%;
  margin: 0;
}
.main-area {
  height: calc(100vh - 64px);
}
.loading-center {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}
</style>
