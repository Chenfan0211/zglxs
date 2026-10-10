<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue';
import type { DataTableColumns, PaginationProps } from 'naive-ui';
import { fetchLaikeOrders } from '@/service/api';
import type { LaikeOrder } from '@/service/api';

const loading = ref(false);
const list = ref<LaikeOrder[]>([]);

const pagination = reactive<PaginationProps>({
  page: 1,
  pageSize: 20,
  itemCount: 0,
  showSizePicker: true,
  pageSizes: [10, 20, 50, 100],
  onChange: page => {
    pagination.page = page;
    loadOrders();
  },
  onUpdatePageSize: pageSize => {
    pagination.pageSize = pageSize;
    pagination.page = 1;
    loadOrders();
  }
});

function formatFen(fen: number | null): string {
  if (fen === null || fen === undefined) {
    return '-';
  }
  return (fen / 100).toFixed(2);
}

function formatTimestamp(ts: number | null): string {
  if (!ts) {
    return '-';
  }
  const date = new Date(ts * 1000);
  return date.toLocaleString();
}

const columns: DataTableColumns<LaikeOrder> = [
  { title: '订单号', key: 'provider_order_id', minWidth: 200 },
  { title: '账号', key: 'account_id', minWidth: 160 },
  {
    title: '状态',
    key: 'order_status',
    width: 90,
    render(row) {
      return row.order_status ?? '-';
    }
  },
  {
    title: '实付金额(元)',
    key: 'pay_amount_fen',
    width: 120,
    align: 'right',
    render(row) {
      return formatFen(row.pay_amount_fen);
    }
  },
  {
    title: '下单时间',
    key: 'create_order_time',
    width: 180,
    render(row) {
      return formatTimestamp(row.create_order_time);
    }
  },
  {
    title: '更新时间',
    key: 'update_order_time',
    width: 180,
    render(row) {
      return formatTimestamp(row.update_order_time);
    }
  },
  { title: '商品ID', key: 'product_id', minWidth: 160 }
];

async function loadOrders() {
  loading.value = true;
  try {
    const { data, error } = await fetchLaikeOrders({
      page_num: pagination.page,
      page_size: pagination.pageSize
    });
    if (!error && data) {
      list.value = data.list || [];
      pagination.itemCount = data.total || 0;
    }
  } finally {
    loading.value = false;
  }
}

onMounted(() => {
  loadOrders();
});
</script>

<template>
  <div class="p-16px">
    <NCard :bordered="false" title="来客订单">
      <NDataTable
        remote
        :loading="loading"
        :columns="columns"
        :data="list"
        :pagination="pagination"
        :bordered="false"
        :scroll-x="1200"
      />
    </NCard>
  </div>
</template>

<style scoped></style>
