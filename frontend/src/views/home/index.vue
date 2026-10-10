<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { useAppStore } from '@/store/modules/app';
import { fetchHomeSummary, fetchNotices } from '@/service/api';
import type { HomeSummary, Notice } from '@/service/api';
import HeaderBanner from './modules/header-banner.vue';
import CardData from './modules/card-data.vue';
import LineChart from './modules/line-chart.vue';
import PieChart from './modules/pie-chart.vue';
import ProjectNews from './modules/project-news.vue';
import CreativityBanner from './modules/creativity-banner.vue';

const appStore = useAppStore();

const gap = computed(() => (appStore.isMobile ? 0 : 16));

const summary = ref<HomeSummary | null>(null);
const notices = ref<Notice[]>([]);

async function loadData() {
  const [{ data: summaryData }, { data: noticeData }] = await Promise.all([
    fetchHomeSummary(),
    fetchNotices()
  ]);

  if (summaryData) {
    summary.value = summaryData;
  }
  if (noticeData) {
    notices.value = noticeData.list || [];
  }
}

onMounted(() => {
  loadData();
});
</script>

<template>
  <NSpace vertical :size="16">
    <NAlert :title="$t('common.tip')" type="warning">
      {{ $t('page.home.branchDesc') }}
    </NAlert>
    <HeaderBanner :summary="summary" />
    <CardData :summary="summary" />
    <NGrid :x-gap="gap" :y-gap="16" responsive="screen" item-responsive>
      <NGi span="24 s:24 m:14">
        <NCard :bordered="false" class="card-wrapper">
          <LineChart :summary="summary" />
        </NCard>
      </NGi>
      <NGi span="24 s:24 m:10">
        <NCard :bordered="false" class="card-wrapper">
          <PieChart :summary="summary" />
        </NCard>
      </NGi>
    </NGrid>
    <NGrid :x-gap="gap" :y-gap="16" responsive="screen" item-responsive>
      <NGi span="24 s:24 m:14">
        <ProjectNews :notices="notices" />
      </NGi>
      <NGi span="24 s:24 m:10">
        <CreativityBanner />
      </NGi>
    </NGrid>
  </NSpace>
</template>

<style scoped></style>
