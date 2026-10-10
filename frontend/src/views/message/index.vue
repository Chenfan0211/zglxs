<script setup lang="ts">
import { h, onMounted, ref } from 'vue';
import { NTag } from 'naive-ui';
import type { DataTableColumns } from 'naive-ui';
import { fetchNotices } from '@/service/api';
import type { Notice } from '@/service/api';

const loading = ref(false);
const list = ref<Notice[]>([]);

const columns: DataTableColumns<Notice> = [
  { title: 'ID', key: 'id', width: 70 },
  { title: '标题', key: 'title', minWidth: 200 },
  { title: '内容', key: 'content', minWidth: 300, ellipsis: { tooltip: true } },
  { title: '类型', key: 'notice_type', width: 100, render: row => ({ system: '系统', notice: '公告' } as Record<string, string>)[row.notice_type] || row.notice_type },
  { title: '状态', key: 'is_published', width: 90, render: row => (row.is_published ? h(NTag, { type: 'success', size: 'small' }, { default: () => '已发布' }) : h(NTag, { type: 'default', size: 'small' }, { default: () => '未发布' })) },
  { title: '时间', key: 'created_at', width: 180, render: row => (row.created_at ? row.created_at.replace('T', ' ').slice(0, 19) : '-') }
];

async function loadData() {
  loading.value = true;
  try {
    const { data, error } = await fetchNotices(true);
    if (!error && data) {
      list.value = data.list || [];
    }
  } finally {
    loading.value = false;
  }
}

onMounted(() => {
  loadData();
});
</script>

<template>
  <div class="p-16px">
    <NCard :bordered="false" title="消息通知">
      <NDataTable :loading="loading" :columns="columns" :data="list" :bordered="false" />
    </NCard>
  </div>
</template>

<style scoped></style>
