<script setup lang="ts">
import { computed, ref } from "vue";
import { AskError, MAX_QUESTION_LENGTH, askQuestion, type AskResponse } from "./api";
import AnswerCard from "./components/AnswerCard.vue";
import AppIcon from "./components/AppIcon.vue";

const EXAMPLES = ["İhbar süresi ne kadar?", "Yıllık izin kaç gün?", "Fazla mesai nasıl ödenir?"];
const REPOSITORY_URL = import.meta.env.VITE_REPOSITORY_URL ?? "";
const THEME_KEY = "theme";

const question = ref("");
const loading = ref(false);
const result = ref<AskResponse | null>(null);
const errorMessage = ref("");
const canSubmit = computed(() => question.value.trim().length > 0 && !loading.value);

async function submit(): Promise<void> {
  if (!canSubmit.value) return;
  loading.value = true;
  result.value = null;
  errorMessage.value = "";
  try {
    result.value = await askQuestion(question.value.trim());
  } catch (error) {
    errorMessage.value =
      error instanceof AskError ? error.message : "Beklenmeyen bir hata oluştu.";
  } finally {
    loading.value = false;
  }
}

function readSavedTheme(): string | null {
  try {
    return localStorage.getItem(THEME_KEY);
  } catch {
    return null; // Storage can be blocked; the theme then simply is not remembered.
  }
}

function applyTheme(theme: string): void {
  document.documentElement.dataset.theme = theme;
  try {
    localStorage.setItem(THEME_KEY, theme);
  } catch {
    // Same as above: the page still works without storage.
  }
}

function toggleTheme(): void {
  const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
  const current = document.documentElement.dataset.theme ?? (prefersDark ? "dark" : "light");
  applyTheme(current === "dark" ? "light" : "dark");
}

const savedTheme = readSavedTheme();
if (savedTheme) document.documentElement.dataset.theme = savedTheme;
</script>

<template>
  <main class="page">
    <header class="header">
      <div>
        <h1>Mevzuat Asistanı</h1>
        <p class="tagline">Türk iş mevzuatı için kaynak gösteren soru-cevap</p>
      </div>
      <button class="theme" type="button" aria-label="Temayı değiştir" @click="toggleTheme">
        <AppIcon name="moon" :size="20" />
      </button>
    </header>

    <p class="notice">
      <AppIcon name="warn" />
      Hukuki danışmanlık değildir. Kişisel bilgi yazmayın; sorular Google tarafından işlenir.
    </p>

    <form class="card ask" @submit.prevent="submit">
      <label for="question">Sorunuzu yazın</label>
      <textarea
        id="question"
        v-model="question"
        :maxlength="MAX_QUESTION_LENGTH"
        placeholder="Örneğin: Yıllık iznimi kullanamıyorum, parası ödenir mi?"
        @keydown.enter.meta.prevent="submit"
        @keydown.enter.ctrl.prevent="submit"
      ></textarea>
      <div class="actions">
        <span class="count">{{ question.length }}/{{ MAX_QUESTION_LENGTH }}</span>
        <button class="primary" type="submit" :disabled="!canSubmit">
          {{ loading ? "Hazırlanıyor" : "Sor" }}
        </button>
      </div>

      <template v-if="!result && !loading && !errorMessage">
        <p class="examples-title">Örnek sorular</p>
        <div class="examples">
          <button
            v-for="example in EXAMPLES"
            :key="example"
            class="chip"
            type="button"
            @click="question = example"
          >
            {{ example }}
          </button>
        </div>
      </template>
    </form>

    <div class="live" aria-live="polite">
      <section v-if="loading" class="card status">
        <p class="status-title">Maddeler taranıyor, cevap hazırlanıyor…</p>
        <p class="status-detail">Bu işlem 30 saniye sürebilir.</p>
      </section>

      <section v-else-if="errorMessage" class="message" role="alert">
        <AppIcon name="warn" :size="20" />
        <div>
          <p class="status-title">Cevap alınamadı</p>
          <p class="status-detail-strong">{{ errorMessage }}</p>
        </div>
      </section>

      <section v-else-if="result && !result.answerable" class="message">
        <AppIcon name="info" :size="20" />
        <div>
          <p class="status-title">Bilmiyorum</p>
          <p class="status-detail-strong">Bu sorunun cevabını eldeki mevzuat metninde bulamadım.</p>
        </div>
      </section>

      <AnswerCard v-else-if="result" :result="result" />
    </div>

    <footer class="footer">
      Kapsam: 4857 sayılı İş Kanunu ve 1475 sayılı Kanun Madde 14 · Metin kontrolü: 1/11/2026
      <template v-if="REPOSITORY_URL">
        · Ölçüm sonuçları:
        <a :href="REPOSITORY_URL" target="_blank" rel="noopener noreferrer">GitHub</a>
      </template>
    </footer>
  </main>
</template>

<style scoped>
.page {
  --page-gap: 24px;
  display: flex;
  flex-direction: column;
  gap: var(--page-gap);
  max-width: 752px; /* 720px of content plus the side padding */
  margin: 0 auto;
  padding: 40px 16px;
}

/* The live region stays in the page so screen readers announce new content. */
.live:empty {
  margin-top: calc(var(--page-gap) * -1);
}

.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

h1 {
  font-size: 26px;
  font-weight: 700;
  line-height: 1.25;
}

.tagline,
.count,
.footer {
  color: var(--muted);
}

.tagline {
  margin-top: 4px;
  font-size: 14px;
}

.theme {
  display: flex;
  padding: 8px;
  border: 0;
  border-radius: 8px;
  background: transparent;
  color: var(--muted);
  cursor: pointer;
}

.theme:hover {
  background: var(--border);
}

.notice {
  display: flex;
  gap: 10px;
  padding: 12px 16px;
  border-radius: 8px;
  background: var(--notice-bg);
  color: var(--notice-text);
  font-size: 14px;
  font-weight: 500;
}

.ask {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

label {
  font-size: 14px;
  font-weight: 600;
}

textarea {
  width: 100%;
  height: 96px;
  padding: 14px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--bg);
  color: var(--text);
  font: inherit;
  font-size: 15px;
  resize: vertical;
}

textarea::placeholder {
  color: var(--muted);
}

.actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.count {
  font-size: 13px;
}

.primary {
  padding: 12px 24px;
  border: 0;
  border-radius: 8px;
  background: var(--accent);
  color: var(--on-accent);
  font: inherit;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
}

.primary:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.examples-title {
  color: var(--muted);
  font-size: 13px;
  font-weight: 500;
}

.examples {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.chip {
  padding: 6px 12px;
  border: 1px solid var(--border);
  border-radius: 999px;
  background: var(--surface);
  color: var(--text);
  font: inherit;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
}

.chip:hover {
  border-color: var(--accent);
}

.status-title {
  font-size: 16px;
  font-weight: 600;
}

.status-detail {
  margin-top: 6px;
  color: var(--muted);
  font-size: 14px;
}

.status-detail-strong {
  margin-top: 4px;
  font-size: 14px;
}

.message {
  display: flex;
  gap: 12px;
  padding: 24px;
  border-radius: 12px;
  background: var(--info-bg);
  color: var(--text);
}

.footer {
  padding: 4px;
  font-size: 13px;
}

.footer a {
  color: inherit;
  font-weight: 500;
}

@media (max-width: 600px) {
  .page {
    --page-gap: 20px;
    padding-top: 24px;
    padding-bottom: 24px;
  }

  h1 {
    font-size: 22px;
  }
}
</style>
