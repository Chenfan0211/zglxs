<script setup lang="ts">
import { h, onMounted, reactive, ref } from 'vue';
import { NTag, NButton } from 'naive-ui';
import type { DataTableColumns } from 'naive-ui';
import { addLiveRoomConsole, delLiveRoomConsole, fetchLiveRoomConsoles } from '@/service/api';
import type { LiveRoomConsole } from '@/service/api';

const loading = ref(false);
const list = ref<LiveRoomConsole[]>([]);

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
const formModel = reactive({ live_room_id: null as number | null, staff_id: null as number | null, console_uid: '', status: true });

const columns: DataTableColumns<LiveRoomConsole> = [
  { title: 'ID', key: 'id', width: 70 },
  { title: '直播间ID', key: 'live_room_id', width: 100 },
  { title: '中控', key: 'nickname', minWidth: 130, render: row => row.nickname || `员工${row.staff_id}` },
  { title: '中控uid', key: 'console_uid', minWidth: 130, render: row => row.console_uid || '-' },
  { title: '员工ID', key: 'staff_id', width: 90 },
  { title: '状态', key: 'status', width: 90, render: row => (row.status ? h(NTag, { type: 'success', size: 'small' }, { default: () => '启用' }) : h(NTag, { type: 'default', size: 'small' }, { default: () => '禁用' })) },
  {
    title: '操作',
    key: 'actions',
    width: 120,
    render(row) {
      return h(NButton, { size: 'small', type: 'error', onClick: () => handleDelete(row) }, { default: () => '删除' });
    }
  }
];

async function loadData() {
  loading.value = true;
  try {
    const { data, error } = await fetchLiveRoomConsoles({ page: pagination.page, page_size: pagination.pageSize });
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
  formModel.console_uid = '';
  formModel.status = true;
  showModal.value = true;
}

async function handleSubmit() {
  if (formModel.live_room_id === null || formModel.staff_id === null) {
    window.$message?.warning('直播间和员工不能为空');
    return;
  }
  saving.value = true;
  try {
    const { error } = await addLiveRoomConsole({ live_room_id: formModel.live_room_id, staff_id: formModel.staff_id, console_uid: formModel.console_uid, status: formModel.status });
    if (error) return;
    window.$message?.success('添加成功');
    showModal.value = false;
    loadData();
  } finally {
    saving.value = false;
  }
}

async function handleDelete(row: LiveRoomConsole) {
  window.$dialog?.warning({
    title: '确认删除',
    content: `确定删除该中控（ID ${row.id}）吗？`,
    positiveText: '删除',
    negativeText: '取消',
    onPositiveClick: async () => {
      const { error } = await delLiveRoomConsole(row.id);
      if (error) return;
      window.$message?.success('删除成功');
      loadData();
    }
  });
}

onMounted(() => {
  loadData();
});
</script>

<template>
  <div class="p-16px">
    <NCard :bordered="false" title="中控管理">
      <template #header-extra>
        <NButton type="primary" @click="openCreate">添加中控</NButton>
      </template>
      <NDataTable :loading="loading" :columns="columns" :data="list" :bordered="false" :pagination="pagination" remote />
    </NCard>

    <NModal v-model:show="showModal" preset="card" title="添加中控" class="w-420px">
      <NForm label-placement="left" label-width="90">
        <NFormItem label="直播间ID">
          <NInputNumber v-model:value="formModel.live_room_id" placeholder="直播间ID" />
        </NFormItem>
        <NFormItem label="员工ID">
          <NInputNumber v-model:value="formModel.staff_id" placeholder="员工ID" />
        </NFormItem>
        <NFormItem label="中控uid">
          <NInput v-model:value="formModel.console_uid" placeholder="中控uid" />
        </NFormItem>
        <NFormItem label="状态">
          <NSwitch v-model:value="formModel.status">
            <template #checked>启用</template>
            <template #unchecked>禁用</template>
          </NSwitch>
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
