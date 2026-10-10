<script setup lang="ts">
import { h, onMounted, reactive, ref } from 'vue';
import { NTag, NButton } from 'naive-ui';
import type { DataTableColumns } from 'naive-ui';
import { addLiveRoomMember, delLiveRoomMember, editLiveRoomMember, fetchLiveRoomMembers } from '@/service/api';
import type { LiveRoomMember } from '@/service/api';

const loading = ref(false);
const list = ref<LiveRoomMember[]>([]);

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
const formModel = reactive({ live_room_id: null as number | null, staff_id: null as number | null, anchor_uid: '', is_control: false, role: 'anchor', status: true });

const columns: DataTableColumns<LiveRoomMember> = [
  { title: 'ID', key: 'id', width: 70 },
  { title: '直播间ID', key: 'live_room_id', width: 100 },
  { title: '主播', key: 'nickname', minWidth: 130, render: row => row.nickname || `员工${row.staff_id}` },
  { title: '主播uid', key: 'anchor_uid', minWidth: 130, render: row => row.anchor_uid || '-' },
  { title: '是否场控', key: 'is_control', width: 100, render: row => (row.is_control ? '是' : '否') },
  { title: '员工ID', key: 'staff_id', width: 90 },
  { title: '角色', key: 'role', width: 90 },
  { title: '状态', key: 'status', width: 90, render: row => (row.status ? h(NTag, { type: 'success', size: 'small' }, { default: () => '启用' }) : h(NTag, { type: 'default', size: 'small' }, { default: () => '禁用' })) },
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
    const { data, error } = await fetchLiveRoomMembers({ page: pagination.page, page_size: pagination.pageSize });
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
  formModel.live_room_id = null;
  formModel.staff_id = null;
  formModel.anchor_uid = '';
  formModel.is_control = false;
  formModel.role = 'anchor';
  formModel.status = true;
  showModal.value = true;
}

function openEdit(row: LiveRoomMember) {
  editingId.value = row.id;
  formModel.live_room_id = row.live_room_id;
  formModel.staff_id = row.staff_id;
  formModel.anchor_uid = row.anchor_uid || '';
  formModel.is_control = row.is_control;
  formModel.role = row.role;
  formModel.status = row.status;
  showModal.value = true;
}

async function handleSubmit() {
  if (formModel.live_room_id === null || formModel.staff_id === null) {
    window.$message?.warning('直播间和员工不能为空');
    return;
  }
  saving.value = true;
  try {
    const payload = { live_room_id: formModel.live_room_id, staff_id: formModel.staff_id, anchor_uid: formModel.anchor_uid, is_control: formModel.is_control, role: formModel.role, status: formModel.status };
    if (editingId.value === null) {
      const { error } = await addLiveRoomMember(payload);
      if (error) return;
      window.$message?.success('添加成功');
    } else {
      const { error } = await editLiveRoomMember({ id: editingId.value, ...payload });
      if (error) return;
      window.$message?.success('更新成功');
    }
    showModal.value = false;
    loadData();
  } finally {
    saving.value = false;
  }
}

async function handleDelete(row: LiveRoomMember) {
  window.$dialog?.warning({
    title: '确认删除',
    content: `确定删除该主播（ID ${row.id}）吗？`,
    positiveText: '删除',
    negativeText: '取消',
    onPositiveClick: async () => {
      const { error } = await delLiveRoomMember(row.id);
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
    <NCard :bordered="false" title="主播管理">
      <template #header-extra>
        <NButton type="primary" @click="openCreate">添加主播</NButton>
      </template>
      <NDataTable :loading="loading" :columns="columns" :data="list" :bordered="false" :pagination="pagination" remote />
    </NCard>

    <NModal v-model:show="showModal" preset="card" :title="editingId === null ? '添加主播' : '编辑主播'" class="w-420px">
      <NForm label-placement="left" label-width="90">
        <NFormItem label="直播间ID">
          <NInputNumber v-model:value="formModel.live_room_id" placeholder="直播间ID" />
        </NFormItem>
        <NFormItem label="员工ID">
          <NInputNumber v-model:value="formModel.staff_id" placeholder="员工ID" />
        </NFormItem>
        <NFormItem label="主播uid">
          <NInput v-model:value="formModel.anchor_uid" placeholder="主播uid" />
        </NFormItem>
        <NFormItem label="是否场控">
          <NSwitch v-model:value="formModel.is_control">
            <template #checked>是</template>
            <template #unchecked>否</template>
          </NSwitch>
        </NFormItem>
        <NFormItem label="角色">
          <NSelect v-model:value="formModel.role" :options="[{ label: '主播', value: 'anchor' }, { label: '助播', value: 'co-anchor' }]" />
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
