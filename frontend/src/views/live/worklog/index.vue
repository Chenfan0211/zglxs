<script setup lang="ts">
import { h, onMounted, reactive, ref } from 'vue';
import { NTag } from 'naive-ui';
import type { DataTableColumns } from 'naive-ui';
import { addWorkLog, fetchWorkLogs } from '@/service/api';
import type { WorkLog } from '@/service/api';

const loading = ref(false);
const list = ref<WorkLog[]>([]);

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

const showModal = ref(false);
const saving = ref(false);
const formModel = reactive({ live_room_id: null as number | null, staff_id: null as number | null, work_type: 'start', remark: '' });

const columns: DataTableColumns<WorkLog> = [
  { title: 'ID', key: 'id', width: 70 },
  { title: '直播间ID', key: 'live_room_id', width: 100, render: row => row.live_room_id ?? '-' },
  { title: '员工ID', key: 'staff_id', width: 90, render: row => row.staff_id ?? '-' },
  {
    title: '类型',
    key: 'work_type',
    width: 100,
    render: row => { const label = ({ start: '上班', end: '下班' } as Record<string, string>)[row.work_type] || row.work_type; const type = row.work_type === 'start' ? 'success' : 'info'; return h(NTag, { type, size: 'small' }, { default: () => label }); }
  },
  { title: '备注', key: 'remark', minWidth: 200, render: row => row.remark || '-' },
  {
    title: '时间',
    key: 'created_at',
    width: 180,
    render: row => (row.created_at ? row.created_at.replace('T', ' ').slice(0, 19) : '-')
  }
];

async function loadData() {
  loading.value = true;
  try {
    const { data, error } = await fetchWorkLogs({ page: pagination.page, page_size: pagination.pageSize });
    if (!error && data) {
      list.value = data.list || [];
      pagination.itemCount = data.total || 0;
    }
  } finally {
    loading.value = false;
  }
}

function openCreate() {
  formModel.live_room_id = null;
  formModel.staff_id = null;
  formModel.work_type = 'start';
  formModel.remark = '';
  showModal.value = true;
}

async function handleSubmit() {
  saving.value = true;
  try {
    const { error } = await addWorkLog({ live_room_id: formModel.live_room_id, staff_id: formModel.staff_id, work_type: formModel.work_type, remark: formModel.remark });
    if (error) return;
    window.$message?.success('记录成功');
    showModal.value = false;
    loadData();
  } finally {
    saving.value = false;
  }
}

onMounted(() => {
  loadData();
});
</script>

<template>
  <div class="p-16px">
    <NCard :bordered="false" title="工作日志">
      <template #header-extra>
        <NButton type="primary" @click="openCreate">记录上下班</NButton>
      </template>
      <NDataTable :loading="loading" :columns="columns" :data="list" :bordered="false" :pagination="pagination" remote />
    </NCard>

    <NModal v-model:show="showModal" preset="card" title="记录上下班" class="w-440px">
      <NForm label-placement="left" label-width="90">
        <NFormItem label="直播间ID">
          <NInputNumber v-model:value="formModel.live_room_id" placeholder="直播间ID" clearable />
        </NFormItem>
        <NFormItem label="员工ID">
          <NInputNumber v-model:value="formModel.staff_id" placeholder="员工ID" clearable />
        </NFormItem>
        <NFormItem label="类型">
          <NSelect v-model:value="formModel.work_type" :options="[{ label: '上班', value: 'start' }, { label: '下班', value: 'end' }]" />
        </NFormItem>
        <NFormItem label="备注">
          <NInput v-model:value="formModel.remark" type="textarea" :rows="3" placeholder="备注" />
        </NFormItem>
      </NForm>
      <template #footer>
        <div class="flex justify-end gap-12px">
          <NButton @click="showModal = false">取消</NButton>
          <NButton type="primary" :loading="saving" @click="handleSubmit">保存</NButton>
        </div>
      </template>
    </NModal>
  </div>
</template>

<style scoped></style>
