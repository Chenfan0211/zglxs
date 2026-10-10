<script setup lang="ts">
import { h, onMounted, reactive, ref } from 'vue';
import { useRouterPush } from '@/hooks/common/router';
import { NTag, NButton } from 'naive-ui';
import type { DataTableColumns } from 'naive-ui';
import { fetchOrderList } from '@/service/api';
import type { OrderItem } from '@/service/api';

const { routerPush } = useRouterPush();

const loading = ref(false);
const list = ref<OrderItem[]>([]);
const filter = reactive({ order_id: '', account_id: '', order_status: null as number | null });

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

function formatFen(fen: number | null | undefined): string {
  if (fen === null || fen === undefined) return '-';
  return (fen / 100).toFixed(2);
}

function formatTime(ts: number | null | undefined): string {
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
  { title: '订单编号', key: 'order_no', minWidth: 190, fixed: 'left' },
  { title: '订单状态', key: 'order_status_str', width: 100, render: row => renderOrderStatus(row) },
  { title: '产品名称', key: 'product_name', minWidth: 150, render: row => row.product_name || row.subject_id || '-' },
  { title: '商品ID', key: 'product_id', minWidth: 130, render: row => row.product_id || '-' },
  { title: '手机号', key: 'user_tel', minWidth: 130, render: row => row.user_tel || '-' },
  { title: '手机尾号', key: 'user_tel_end', width: 90, render: row => row.user_tel_end || '-' },
  { title: '支付时间', key: 'pay_time', width: 170, render: row => formatTime(row.pay_time) },
  { title: '支付金额(元)', key: 'verify_amount', width: 120, align: 'right', render: row => formatFen(row.verify_amount) },
  { title: '直播部', key: 'department_name', width: 100, render: row => row.department_name || '-' },
  { title: '直播间', key: 'live_name', width: 120, render: row => row.live_name || '-' },
  { title: '主播', key: 'anchor_name', width: 100, render: row => row.anchor_name || '-' },
  { title: '转化部', key: 'custom_department_name', width: 100, render: row => row.custom_department_name || '-' },
  { title: '客服组', key: 'custom_service_group_name', width: 100, render: row => row.custom_service_group_name || '-' },
  { title: '客服分类', key: 'custom_cate_name', width: 100, render: row => row.custom_cate_name || '-' },
  { title: '客服', key: 'custom_name', width: 100, render: row => row.custom_name || '-' },
  { title: '跟单状态', key: 'follow_status_str', width: 100, render: row => row.follow_status_str || '-' },
  { title: '备注', key: 'memo', minWidth: 150, render: row => row.memo || '-' },
  {
    title: '操作',
    key: 'actions',
    width: 100,
    fixed: 'right',
    render(row) {
      return h(NButton, { size: 'small', type: 'primary', onClick: () => goDetail(row) }, { default: () => '详情' });
    }
  }
];

async function loadData() {
  loading.value = true;
  try {
    const { data, error } = await fetchOrderList({
      page: pagination.page,
      page_size: pagination.pageSize,
      order_id: filter.order_id,
      account_id: filter.account_id,
      order_status: filter.order_status
    });
    if (!error && data) {
      list.value = data.list || [];
      pagination.itemCount = data.total || 0;
    }
  } finally {
    loading.value = false;
  }
}

function goDetail(row: OrderItem) {
  routerPush({ name: 'order_detail', query: { order_id: row.order_no } });
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
    <NCard :bordered="false" title="订单管理">
      <template #header-extra>
        <NSpace>
          <NInput v-model:value="filter.order_id" placeholder="订单编号" clearable class="w-180px" @keyup.enter="handleSearch" />
          <NInput v-model:value="filter.account_id" placeholder="账号" clearable class="w-140px" @keyup.enter="handleSearch" />
          <NButton type="primary" @click="handleSearch">查询</NButton>
        </NSpace>
      </template>
      <NDataTable :loading="loading" :columns="columns" :data="list" :bordered="false" :pagination="pagination" remote :scroll-x="2200" />
    </NCard>
  </div>
</template>

<style scoped></style>
