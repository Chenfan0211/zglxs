<script setup lang="ts">
import { h, onMounted, reactive, ref } from 'vue';
import { NButton } from 'naive-ui';
import type { DataTableColumns } from 'naive-ui';
import { addLiveRoom, delLiveRoom, editLiveRoom, fetchLiveRooms } from '@/service/api';
import type { LiveRoom } from '@/service/api';

const loading = ref(false);
const list = ref<LiveRoom[]>([]);
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

const showModal = ref(false);
const editingId = ref<number | null>(null);
const saving = ref(false);
const formModel = reactive({ live_name: '', live_uid: '', live_uuid: '', department_id: null as number | null, memo: '', ordid: 0 });

const columns: DataTableColumns<LiveRoom> = [
  { title: 'ID', key: 'id', width: 70 },
  { title: '直播间名', key: 'live_name', minWidth: 150 },
  { title: '抖音uid', key: 'live_uid', minWidth: 150, render: row => row.live_uid || '-' },
  { title: '抖音号', key: 'live_uuid', minWidth: 130, render: row => row.live_uuid || '-' },
  { title: '部门', key: 'department_name', width: 120, render: row => row.department_name || '-' },
  { title: '备注', key: 'memo', minWidth: 150, render: row => row.memo || '-' },
  { title: '排序号', key: 'ordid', width: 90, align: 'center' },
  {
    title: '操作',
    key: 'actions',
    width: 160,
    render(row) {
      return h('div', { class: 'flex gap-8px' }, [
        h(NButton, { size: 'small', type: 'primary', onClick: () => openEdit(row) }, { default: () => '编辑' }),
        h(NButton, { size: 'small', type: 'error', onClick: () => handleDelete(row) }, { default: () => '删除' })
      ]);
    }
  }
];

async function loadData() {
  loading.value = true;
  try {
    const { data, error } = await fetchLiveRooms({ page: pagination.page, page_size: pagination.pageSize, keyword: keyword.value });
    if (!error && data) {
      list.value = data.list || [];
      pagination.itemCount = data.total || 0;
    }
  } finally {
    loading.value = false;
  }
}

function openCreate() {
  editingId.value = null;
  formModel.live_name = '';
  formModel.live_uid = '';
  formModel.live_uuid = '';
  formModel.department_id = null;
  formModel.memo = '';
  formModel.ordid = 0;
  showModal.value = true;
}

function openEdit(row: LiveRoom) {
  editingId.value = row.id;
  formModel.live_name = row.live_name || row.name;
  formModel.live_uid = row.live_uid || '';
  formModel.live_uuid = row.live_uuid || '';
  formModel.department_id = row.department_id;
  formModel.memo = row.memo || '';
  formModel.ordid = row.ordid;
  showModal.value = true;
}

async function handleSubmit() {
  if (!formModel.live_name.trim()) {
    window.$message?.warning('直播间名称不能为空');
    return;
  }
  saving.value = true;
  try {
    const payload = {
      name: formModel.live_name,
      live_uid: formModel.live_uid,
      live_uuid: formModel.live_uuid,
      department_id: formModel.department_id,
      memo: formModel.memo,
      ordid: formModel.ordid
    };
    if (editingId.value === null) {
      const { error } = await addLiveRoom(payload);
      if (error) return;
      window.$message?.success('新增成功');
    } else {
      const { error } = await editLiveRoom({ id: editingId.value, ...payload });
      if (error) return;
      window.$message?.success('编辑成功');
    }
    showModal.value = false;
    loadData();
  } finally {
    saving.value = false;
  }
}

async function handleDelete(row: LiveRoom) {
  window.$dialog?.warning({
    title: '确认删除',
    content: `确定删除直播间「${row.live_name || row.name}」吗？`,
    positiveText: '确定',
    negativeText: '取消',
    onPositiveClick: async () => {
      const { error } = await delLiveRoom(row.id);
      if (error) return;
      window.$message?.success('删除成功');
      loadData();
    }
  });
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
    <NCard :bordered="false" title="直播间管理">
      <template #header-extra>
        <NSpace>
          <NInput v-model:value="keyword" placeholder="输入关键字" clearable class="w-180px" @keyup.enter="handleSearch" />
          <NButton type="primary" @click="handleSearch">筛选</NButton>
          <NButton type="primary" @click="openCreate">新增直播间</NButton>
        </NSpace>
      </template>
      <NDataTable :loading="loading" :columns="columns" :data="list" :bordered="false" :pagination="pagination" remote :scroll-x="1100" />
    </NCard>

    <NModal v-model:show="showModal" preset="card" :title="editingId === null ? '新增直播间' : '编辑直播间'" class="w-560px">
      <NForm label-placement="left" label-width="100">
        <NFormItem label="直播间名：">
          <NInput v-model:value="formModel.live_name" placeholder="请输入直播间名" />
        </NFormItem>
        <NFormItem label="抖音uid：">
          <NInput v-model:value="formModel.live_uid" placeholder="请输入抖音用户uid（来客商户账号为商户抖音号，填0）" />
        </NFormItem>
        <NFormItem label="抖音号：">
          <NInput v-model:value="formModel.live_uuid" placeholder="请输入抖音号" />
        </NFormItem>
        <NFormItem label="部门：">
          <NInputNumber v-model:value="formModel.department_id" placeholder="部门ID" clearable />
        </NFormItem>
        <NFormItem label="备注：">
          <NInput v-model:value="formModel.memo" type="textarea" :rows="2" placeholder="请输入备注" />
        </NFormItem>
        <NFormItem label="排序：">
          <NInputNumber v-model:value="formModel.ordid" placeholder="请输入排序号" />
        </NFormItem>
      </NForm>
      <template #footer>
        <div class="flex justify-end gap-12px">
          <NButton @click="showModal = false">取消</NButton>
          <NButton type="primary" :loading="saving" @click="handleSubmit">确定</NButton>
        </div>
      </template>
    </NModal>
  </div>
</template>

<style scoped></style>
