<script setup lang="ts">
import { h, onMounted, reactive, ref } from 'vue';
import { NTag } from 'naive-ui';
import type { DataTableColumns } from 'naive-ui';
import { fetchReservationList } from '@/service/api';
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


const ORDER_STATUS_MAP: Record<number, { label: string; type: 'default' | 'success' | 'warning' | 'error' | 'info' }> = {
  0: { label: '待付款', type: 'warning' },
  1: { label: '待发货', type: 'info' },
  2: { label: '待收货', type: 'info' },
  3: { label: '已完成', type: 'success' },
  4: { label: '已取消', type: 'default' },
  5: { label: '退款中', type: 'warning' },
  6: { label: '已退款', type: 'error' }
};

function renderOrderStatus(row: OrderItem) {
  const status = row.order_status ?? null;
  const item = status !== null ? ORDER_STATUS_MAP[status] : undefined;
  if (!item) return row.order_status_str || '-';
  return h(NTag, { type: item.type, size: 'small' }, { default: () => item.label });
}

const columns: DataTableColumns<OrderItem> = [
  { title: '订单编号', key: 'order_no', minWidth: 180, fixed: 'left' },
  { title: '订单状态', key: 'order_status_str', width: 100, render: row => renderOrderStatus(row) },
  { title: '产品名称', key: 'product_name', minWidth: 140, render: row => row.product_name || '-' },
  { title: '手机号', key: 'user_tel', minWidth: 130, render: row => row.user_tel || '-' },
  { title: '支付时间', key: 'pay_time', width: 170, render: row => fmtTime(row.pay_time) },
  { title: '支付金额(元)', key: 'verify_amount', width: 120, align: 'right', render: row => fmtFen(row.verify_amount) },
  { title: '直播间', key: 'live_name', width: 110, render: row => row.live_name || '-' },
  { title: '主播', key: 'anchor_name', width: 100, render: row => row.anchor_name || '-' },
  { title: '客服', key: 'custom_name', width: 100, render: row => row.custom_name || '-' },
  { title: '客服组', key: 'custom_service_group_name', width: 100, render: row => row.custom_service_group_name || '-' },
  { title: '备注', key: 'memo', minWidth: 140, render: row => row.memo || '-' }
];

async function loadData() {
  loading.value = true;
  try {
    const { data, error } = await fetchReservationList({ page: pagination.page, page_size: pagination.pageSize, order_id: keyword.value });
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
    <NCard :bordered="false" title="预约管理">
      <template #header-extra>
        <NSpace>
          <NInput v-model:value="keyword" placeholder="订单编号" clearable class="w-180px" @keyup.enter="handleSearch" />
          <NButton type="primary" @click="handleSearch">查询</NButton>
        </NSpace>
      </template>
      <NDataTable :loading="loading" :columns="columns" :data="list" :bordered="false" :pagination="pagination" remote :scroll-x="1600" />
    </NCard>
  </div>
</template>

<style scoped></style>
