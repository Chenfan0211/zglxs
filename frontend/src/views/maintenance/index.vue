<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue';
import type { DataTableColumns } from 'naive-ui';
import { fetchClaimCustomList } from '@/service/api';
import type { OrderItem } from '@/service/api';

const loading = ref(false);
const list = ref<OrderItem[]>([]);
const keyword = ref('');

const pagination = reactive({
  page: 1,
  pageSize: 20,
  itemCount: 0,
  showSizePicker: true,
  pageSizes: [10, 20, 50, 100],
  onChange: (page: number) => {
    pagination.page = page;
    loadData();
  },
  onUpdatePageSize: (pageSize: number) => {
    pagination.pageSize = pageSize;
    pagination.page = 1;
    loadData();
  }
});

function fmtFen(v: number | null | undefined): string {
  return v === null || v === undefined ? '-' : (v / 100).toFixed(2);
}

function fmtTime(ts: number | null | undefined): string {
  if (!ts) return '-';
  return new Date(ts * 1000).toLocaleString();
}

const columns: DataTableColumns<OrderItem> = [
  { title: '订单编号', key: 'order_no', minWidth: 180, fixed: 'left' },
  { title: '产品名称', key: 'product_name', minWidth: 140, render: row => row.product_name || '-' },
  { title: '手机号', key: 'user_tel', minWidth: 130, render: row => row.user_tel || '-' },
  { title: '支付时间', key: 'pay_time', width: 170, render: row => fmtTime(row.pay_time) },
  { title: '支付金额(元)', key: 'verify_amount', width: 120, align: 'right', render: row => fmtFen(row.verify_amount) },
  { title: '售后部', key: 'maintenance_department_name', width: 110, render: row => row.maintenance_department_name || '-' },
  { title: '售后', key: 'maintenance_name', width: 100, render: row => row.maintenance_name || '-' },
  { title: '退款类型', key: 'refund_type_str', width: 100, render: row => row.refund_type_str || '-' },
  { title: '退款金额(元)', key: 'refund_money', width: 120, align: 'right', render: row => fmtFen(row.refund_money) },
  { title: '备注', key: 'memo', minWidth: 140, render: row => row.memo || '-' }
];

async function loadData() {
  loading.value = true;
  try {
    const { data, error } = await fetchClaimCustomList({ page: pagination.page, page_size: pagination.pageSize, order_id: keyword.value });
    if (!error && data) {
      list.value = data.list || [];
      pagination.itemCount = data.total || 0;
    }
  } finally {
    loading.value = false;
  }
}

function handleSearch() {
  pagination.page = 1;
  loadData();
}

onMounted(() => {
  loadData();
});
</script>

<template>
  <div class="p-16px">
    <NCard :bordered="false" title="售后管理">
      <template #header-extra>
        <NSpace>
          <NInput v-model:value="keyword" placeholder="订单编号" clearable class="w-180px" @keyup.enter="handleSearch" />
          <NButton type="primary" @click="handleSearch">查询</NButton>
        </NSpace>
      </template>
      <NDataTable :loading="loading" :columns="columns" :data="list" :bordered="false" :pagination="pagination" remote :scroll-x="1400" />
    </NCard>
  </div>
</template>

<style scoped></style>
