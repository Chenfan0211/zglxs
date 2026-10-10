<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { fetchFinanceStatistic, fetchHomeSummary } from '@/service/api';

const loading = ref(false);
const summary = ref<{ cards?: { total_orders: number; total_amount_fen: number; today_orders: number; today_amount_fen: number } } | null>(null);
const finance = ref<{ total_orders: number; paid_orders: number; total_amount_fen: number } | null>(null);

function fmtFen(v: number): string {
  return (v / 100).toFixed(2);
}

async function loadData() {
  loading.value = true;
  try {
    const [{ data: s }, { data: f }] = await Promise.all([fetchHomeSummary(), fetchFinanceStatistic()]);
    if (s) summary.value = s as never;
    if (f) finance.value = f;
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
    <NGrid :x-gap="16" :y-gap="16" cols="s:1 m:2 l:4">
      <NGi>
        <NCard :bordered="false" title="累计订单" size="small">
          <div class="text-28px font-bold">{{ summary?.cards?.total_orders ?? 0 }}</div>
        </NCard>
      </NGi>
      <NGi>
        <NCard :bordered="false" title="今日订单" size="small">
          <div class="text-28px font-bold">{{ summary?.cards?.today_orders ?? 0 }}</div>
        </NCard>
      </NGi>
      <NGi>
        <NCard :bordered="false" title="累计成交额(元)" size="small">
          <div class="text-28px font-bold">{{ summary ? fmtFen(summary.cards?.total_amount_fen ?? 0) : '0.00' }}</div>
        </NCard>
      </NGi>
      <NGi>
        <NCard :bordered="false" title="已支付订单" size="small">
          <div class="text-28px font-bold">{{ finance?.paid_orders ?? 0 }}</div>
        </NCard>
      </NGi>
    </NGrid>

    <NCard :bordered="false" title="系统说明" class="mt-16px">
      <NAlert type="info">
        控制台工作台展示核心运营数据。订单、财务等数据来自来客同步库，配置来客凭据后将展示真实数据。
      </NAlert>
    </NCard>
  </div>
</template>

<style scoped></style>
