<script setup lang="ts">
import { onMounted, ref } from 'vue';
import type { DataTableColumns } from 'naive-ui';
import { fetchFinanceStatistic } from '@/service/api';
import type { FinanceStatistic } from '@/service/api';

const loading = ref(false);
const stat = ref<FinanceStatistic | null>(null);

function formatFen(fen: number): string {
  return (fen / 100).toFixed(2);
}

const columns: DataTableColumns<{ status: number; label: string; count: number; amount_fen: number }> = [
  { title: '状态', key: 'label', minWidth: 120 },
  { title: '订单数', key: 'count', width: 120, align: 'right' },
  { title: '金额(元)', key: 'amount_fen', width: 150, align: 'right', render: row => formatFen(row.amount_fen) }
];

async function loadData() {
  loading.value = true;
  try {
    const { data, error } = await fetchFinanceStatistic();
    if (!error && data) {
      stat.value = data;
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
    <NGrid :x-gap="16" :y-gap="16" cols="s:1 m:3">
      <NGi>
        <NCard :bordered="false" title="总订单数" size="small">
          <div class="text-28px font-bold">{{ stat?.total_orders ?? 0 }}</div>
        </NCard>
      </NGi>
      <NGi>
        <NCard :bordered="false" title="已支付订单" size="small">
          <div class="text-28px font-bold">{{ stat?.paid_orders ?? 0 }}</div>
        </NCard>
      </NGi>
      <NGi>
        <NCard :bordered="false" title="总成交额(元)" size="small">
          <div class="text-28px font-bold">{{ stat ? formatFen(stat.total_amount_fen) : '0.00' }}</div>
        </NCard>
      </NGi>
    </NGrid>

    <NCard :bordered="false" title="状态分布" class="mt-16px">
      <NDataTable :loading="loading" :columns="columns" :data="stat?.status_list || []" :bordered="false" />
    </NCard>
  </div>
</template>

<style scoped></style>
