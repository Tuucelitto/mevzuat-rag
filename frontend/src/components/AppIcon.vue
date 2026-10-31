<script setup lang="ts">
import { computed } from "vue";
import ext from "../assets/icons/ext.svg";
import info from "../assets/icons/info.svg";
import moon from "../assets/icons/moon.svg";
import warn from "../assets/icons/warn.svg";

const icons = { ext, info, moon, warn };

const props = withDefaults(defineProps<{ name: keyof typeof icons; size?: number }>(), {
  size: 18,
});

// The file acts as a mask and currentColor paints it, so icons follow the theme.
const style = computed(() => ({
  width: `${props.size}px`,
  height: `${props.size}px`,
  maskImage: `url("${icons[props.name]}")`,
}));
</script>

<template>
  <span class="icon" :style="style" aria-hidden="true"></span>
</template>

<style scoped>
.icon {
  display: inline-block;
  flex: none;
  background-color: currentColor;
  mask-repeat: no-repeat;
  mask-position: center;
  mask-size: contain;
}
</style>
