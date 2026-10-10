<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue';
import type { DataTableColumns } from 'naive-ui';
import { fetchSettlementList } from '@/service/api';
import type { SettlementItem } from '@/service/api';

const loading = ref(false);
const list = ref<SettlementItem[]>([]);

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

function fmtFen(v: unknown): string {
  const n = Number(v);
  return Number.isNaN(n) || v === null || v === undefined ? '-' : (n / 100).toFixed(2);
}

function fmtTime(ts: number | null): string {
  if (!ts) return '-';
  return new Date(ts * 1000).toLocaleString();
}

const columns: DataTableColumns<SettlementItem> = [
  { title: '订单编号', key: 'order_no', minWidth: 180, fixed: 'left' },
  { title: '商品ID', key: 'product_id', minWidth: 120, render: row => row.product_id || '-' },
  { title: '直连商品编码', key: 'out_product_id', minWidth: 120, render: row => row.out_product_id || '-' },
  { title: '产品名称', key: 'product_name', minWidth: 140, render: row => row.product_name || '-' },
  { title: '手机号', key: 'user_tel', minWidth: 120, render: row => row.user_tel || '-' },
  { title: '支付时间', key: 'pay_time', width: 160, render: row => fmtTime(row.pay_time) },
  { title: '核销金额', key: 'verify_amount', width: 110, align: 'right', render: row => fmtFen(row.verify_amount) },
  { title: '补差价', key: 'add_price', width: 100, align: 'right', render: row => fmtFen(row.add_price) },
  { title: '成本', key: 'cost_amount', width: 100, align: 'right', render: row => fmtFen(row.cost_amount) },
  { title: '利润', key: 'profit_amount', width: 100, align: 'right', render: row => fmtFen(row.profit_amount) },
  { title: '平台服务费', key: 'total_merchant_platform_service', width: 110, align: 'right', render: row => fmtFen(row.total_merchant_platform_service) },
  { title: '达人佣金', key: 'talent_commission', width: 100, align: 'right', render: row => fmtFen(row.talent_commission) },
  { title: '券码', key: 'certificate_code', width: 120, render: row => row.certificate_code || '-' },
  { title: '转化部', key: 'custom_department_name', width: 100, render: row => row.custom_department_name || '-' },
  { title: '客服组', key: 'custom_service_group_name', width: 100, render: row => row.custom_service_group_name || '-' },
  { title: '客服', key: 'custom_name', width: 100, render: row => row.custom_name || '-' },
  { title: '直播部', key: 'department_name', width: 100, render: row => row.department_name || '-' },
  { title: '直播间', key: 'live_name', width: 110, render: row => row.live_name || '-' },
  { title: '主播', key: 'anchor_name', width: 90, render: row => row.anchor_name || '-' },
  { title: '带货人', key: 'sale_user_name', width: 90, render: row => row.sale_user_name || '-' },
  { title: '退款类型', key: 'refund_type_str', width: 100, render: row => row.refund_type_str || '-' }
];

async function loadData() {
  loading.value = true;
  try {
    const { data, error } = await fetchSettlementList({ page: pagination.page, page_size: pagination.pageSize });
    if (!error && data) {
      list.value = data.list || [];
      pagination.itemCount = data.total || 0;
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
    <NCard :bordered="false" title="结算列表">
      <NDataTable :loading="loading" :columns="columns" :data="list" :bordered="false" :pagination="pagination" remote :scroll-x="2400" />
    </NCard>
  </div>
</template>

<style scoped></style>
