<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue';
import { useRoute } from 'vue-router';
import { claimOrder, fetchFollowLogs, fetchOrderDetail, updateFollow } from '@/service/api';
import type { FollowLog, OrderFollow } from '@/service/api';

const route = useRoute();
const orderId = (route.query.order_id as string) || '';

const loading = ref(false);
const order = ref<Record<string, unknown> | null>(null);
const follow = ref<OrderFollow | null>(null);
const followLogs = ref<FollowLog[]>([]);

const followForm = reactive({ follow_status: 'new', owner_staff_id: null as number | null, memo: '', tel: '' });
const saving = ref(false);

const statusOptions = [
  { label: '待跟进', value: 'new' },
  { label: '跟进中', value: 'following' },
  { label: '已完成', value: 'done' },
  { label: '无效', value: 'invalid' }
];

async function loadData() {
  loading.value = true;
  try {
    const [{ data: detailData }, { data: logData }] = await Promise.all([
      fetchOrderDetail(orderId),
      fetchFollowLogs({ order_id: orderId, page: 1, page_size: 50 })
    ]);
    if (detailData) {
      order.value = detailData as unknown as Record<string, unknown>;
      follow.value = detailData.follow ?? null;
      if (detailData.follow) {
        followForm.follow_status = detailData.follow.follow_status;
        followForm.owner_staff_id = detailData.follow.owner_staff_id;
        followForm.memo = detailData.follow.memo || '';
        followForm.tel = detailData.follow.tel || '';
      }
    }
    if (logData) {
      followLogs.value = logData.list || [];
    }
  } finally {
    loading.value = false;
  }
}

async function handleFollow() {
  saving.value = true;
  try {
    const { error } = await updateFollow({
      order_id: orderId,
      follow_status: followForm.follow_status,
      owner_staff_id: followForm.owner_staff_id,
      memo: followForm.memo,
      tel: followForm.tel,
      action: 'follow'
    });
    if (error) return;
    window.$message?.success('跟进已更新');
    loadData();
  } finally {
    saving.value = false;
  }
}

async function handleClaim() {
  const { error } = await claimOrder(orderId);
  if (error) return;
  window.$message?.success('认领成功');
}

function formatFen(fen: unknown): string {
  const n = Number(fen);
  return Number.isNaN(n) ? '-' : (n / 100).toFixed(2);
}

function formatTime(ts: unknown): string {
  const n = Number(ts);
  if (!n) return '-';
  return new Date(n * 1000).toLocaleString();
}

onMounted(() => {
  loadData();
});
</script>

<template>
  <div class="p-16px">
    <NCard :bordered="false" title="订单详情" :loading="loading">
      <NDescriptions v-if="order" :column="2" bordered size="small">
        <NDescriptionsItem label="订单号">{{ order.provider_order_id }}</NDescriptionsItem>
        <NDescriptionsItem label="账号">{{ order.account_id || '-' }}</NDescriptionsItem>
        <NDescriptionsItem label="状态">{{ order.order_status ?? '-' }}</NDescriptionsItem>
        <NDescriptionsItem label="实付金额(元)">{{ formatFen(order.pay_amount_fen) }}</NDescriptionsItem>
        <NDescriptionsItem label="下单时间">{{ formatTime(order.create_order_time) }}</NDescriptionsItem>
        <NDescriptionsItem label="支付时间">{{ formatTime(order.pay_time) }}</NDescriptionsItem>
        <NDescriptionsItem label="商品ID">{{ order.product_id || '-' }}</NDescriptionsItem>
        <NDescriptionsItem label="商品名">{{ order.subject_id || '-' }}</NDescriptionsItem>
      </NDescriptions>
    </NCard>

    <NCard :bordered="false" title="跟进信息" class="mt-16px">
      <NForm label-placement="left" label-width="90" class="max-w-600px">
        <NFormItem label="跟进状态">
          <NSelect v-model:value="followForm.follow_status" :options="statusOptions" />
        </NFormItem>
        <NFormItem label="负责人">
          <NInputNumber v-model:value="followForm.owner_staff_id" placeholder="员工ID" clearable />
        </NFormItem>
        <NFormItem label="联系电话">
          <NInput v-model:value="followForm.tel" placeholder="联系电话" />
        </NFormItem>
        <NFormItem label="备注">
          <NInput v-model:value="followForm.memo" type="textarea" :rows="3" placeholder="跟进备注" />
        </NFormItem>
        <div class="flex gap-12px">
          <NButton type="primary" :loading="saving" @click="handleFollow">保存跟进</NButton>
          <NButton @click="handleClaim">认领订单</NButton>
        </div>
      </NForm>
    </NCard>

    <NCard :bordered="false" title="跟进日志" class="mt-16px">
      <NDataTable
        :columns="[
          { title: 'ID', key: 'id', width: 70 },
          { title: '员工', key: 'staff_name', minWidth: 100, render: r => r.staff_name || '-' },
          { title: '操作', key: 'action', minWidth: 100 },
          { title: '备注', key: 'remark', minWidth: 200, render: r => r.remark || '-' },
          { title: '时间', key: 'created_at', width: 180, render: r => (r.created_at ? r.created_at.replace('T', ' ').slice(0, 19) : '-') }
        ]"
        :data="followLogs"
        :bordered="false"
      />
    </NCard>
  </div>
</template>

<style scoped></style>
