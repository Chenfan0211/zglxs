<script setup lang="ts">
import { computed } from 'vue';
import { $t } from '@/locales';
import type { Notice } from '@/service/api';

defineOptions({
  name: 'ProjectNews'
});

const props = defineProps<{
  notices: Notice[];
}>();

interface NewsItem {
  id: number;
  content: string;
  time: string;
}

const newses = computed<NewsItem[]>(() => {
  return (props.notices || []).map(notice => ({
    id: notice.id,
    content: notice.title,
    time: notice.created_at ? notice.created_at.replace('T', ' ').slice(0, 19) : ''
  }));
});
</script>

<template>
  <NCard :title="$t('page.home.projectNews.title')" :bordered="false" size="small" segmented class="card-wrapper">
    <template #header-extra>
      <a class="text-primary" href="javascript:;">{{ $t('page.home.projectNews.moreNews') }}</a>
    </template>
    <NList v-if="newses.length">
      <NListItem v-for="item in newses" :key="item.id">
        <template #prefix>
          <NAvatar round size="large" class="bg-primary! text-white!">通</NAvatar>
        </template>
        <NThing :title="item.content" :description="item.time" />
      </NListItem>
    </NList>
    <NEmpty v-else description="暂无公告" />
  </NCard>
</template>

<style scoped></style>
