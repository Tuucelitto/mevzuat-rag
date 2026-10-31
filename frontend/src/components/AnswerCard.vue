<script setup lang="ts">
import type { AskResponse } from "../api";
import AppIcon from "./AppIcon.vue";

defineProps<{ result: AskResponse }>();
</script>

<template>
  <section class="card answer" aria-label="Cevap">
    <h2 class="label">Cevap</h2>
    <p class="answer-text">{{ result.answer }}</p>

    <div v-if="result.unanswered_parts" class="unanswered">
      <AppIcon name="info" class="accent" />
      <div>
        <h3>Metinde bulunmayan kısım</h3>
        <p>{{ result.unanswered_parts }}</p>
      </div>
    </div>

    <h2 class="label">Kaynaklar</h2>
    <ul class="sources">
      <li v-for="source in result.sources" :key="source.citation">
        <a :href="source.url" target="_blank" rel="noopener noreferrer">
          {{ source.citation }}
          <AppIcon name="ext" :size="15" />
          <span class="visually-hidden">(resmî metni yeni sekmede açar)</span>
        </a>
      </li>
    </ul>
  </section>
</template>

<style scoped>
.answer {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.label {
  font-size: 13px;
  font-weight: 600;
  color: var(--muted);
}

.answer-text {
  font-size: 16px;
  white-space: pre-line;
}

.unanswered {
  display: flex;
  gap: 10px;
  padding: 14px;
  border-radius: 8px;
  background: var(--info-bg);
}

.unanswered h3 {
  font-size: 13px;
  font-weight: 600;
}

.unanswered p {
  font-size: 14px;
}

.accent {
  color: var(--accent);
}

.sources {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.sources a {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 500;
  color: var(--accent);
  text-decoration: none;
}

.sources a:hover {
  text-decoration: underline;
}
</style>
