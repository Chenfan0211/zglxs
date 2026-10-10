<script setup lang="ts">
import { h, onMounted, reactive, ref } from 'vue';
import { NTag, NButton } from 'naive-ui';
import type { DataTableColumns } from 'naive-ui';
import { addGroupMember, delGroupMember, editGroupMember, fetchGroupMembers } from '@/service/api';
import type { GroupMember } from '@/service/api';

const loading = ref(false);
const list = ref<GroupMember[]>([]);

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
const formModel = reactive({ group_id: null as number | null, staff_id: null as number | null, custom_uid: '', rate: 0, day_limit_num: null as number | null, work_time: '', status: true });

const columns: DataTableColumns<GroupMember> = [
  { title: 'ID', key: 'id', width: 70 },
  { title: '组ID', key: 'group_id', width: 90 },
  { title: '客服名', key: 'custom_name', minWidth: 120, render: row => row.custom_name || '-' },
  { title: '客服uid', key: 'custom_uid', minWidth: 140, render: row => row.custom_uid || '-' },
  { title: '权重', key: 'rate', width: 90, align: 'center' },
  { title: '每日接待限制', key: 'day_limit_num', width: 120, align: 'center', render: row => row.day_limit_num ?? '-' },
  { title: '工作时间', key: 'work_time', minWidth: 140, render: row => row.work_time || '-' },
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
    const { data, error } = await fetchGroupMembers({ page: pagination.page, page_size: pagination.pageSize });
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
  formModel.group_id = null;
  formModel.staff_id = null;
  formModel.custom_uid = '';
  formModel.rate = 0;
  formModel.day_limit_num = null;
  formModel.work_time = '';
  formModel.status = true;
  showModal.value = true;
}

function openEdit(row: GroupMember) {
  editingId.value = row.id;
  formModel.group_id = row.group_id;
  formModel.staff_id = row.staff_id;
  formModel.custom_uid = row.custom_uid || '';
  formModel.rate = row.rate;
  formModel.day_limit_num = row.day_limit_num;
  formModel.work_time = row.work_time || '';
  formModel.status = row.status;
  showModal.value = true;
}

async function handleSubmit() {
  if (formModel.group_id === null || formModel.staff_id === null) {
    window.$message?.warning('组和成员不能为空');
    return;
  }
  saving.value = true;
  try {
    const payload = {
      group_id: formModel.group_id,
      staff_id: formModel.staff_id,
      custom_uid: formModel.custom_uid,
      rate: formModel.rate,
      day_limit_num: formModel.day_limit_num,
      work_time: formModel.work_time,
      status: formModel.status
    };
    if (editingId.value === null) {
      const { error } = await addGroupMember(payload);
      if (error) return;
      window.$message?.success('添加成功');
    } else {
      const { error } = await editGroupMember({ id: editingId.value, ...payload });
      if (error) return;
      window.$message?.success('更新成功');
    }
    showModal.value = false;
    loadData();
  } finally {
    saving.value = false;
  }
}

async function handleDelete(row: GroupMember) {
  window.$dialog?.warning({
    title: '确认删除',
    content: `确定删除该组成员（ID ${row.id}）吗？`,
    positiveText: '确定',
    negativeText: '取消',
    onPositiveClick: async () => {
      const { error } = await delGroupMember(row.id);
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
    <NCard :bordered="false" title="客服组成员">
      <template #header-extra>
        <NButton type="primary" @click="openCreate">新增成员</NButton>
      </template>
      <NDataTable :loading="loading" :columns="columns" :data="list" :bordered="false" :pagination="pagination" remote :scroll-x="1100" />
    </NCard>

    <NModal v-model:show="showModal" preset="card" :title="editingId === null ? '新增成员' : '编辑成员'" class="w-520px">
      <NForm label-placement="left" label-width="110">
        <NFormItem label="组ID">
          <NInputNumber v-model:value="formModel.group_id" placeholder="组ID" />
        </NFormItem>
        <NFormItem label="员工ID">
          <NInputNumber v-model:value="formModel.staff_id" placeholder="员工ID" />
        </NFormItem>
        <NFormItem label="客服uid">
          <NInput v-model:value="formModel.custom_uid" placeholder="客服uid" />
        </NFormItem>
        <NFormItem label="权重">
          <NInputNumber v-model:value="formModel.rate" placeholder="请输入权重" />
        </NFormItem>
        <NFormItem label="每日接待限制">
          <NInputNumber v-model:value="formModel.day_limit_num" placeholder="请输入每日接待限制" clearable />
        </NFormItem>
        <NFormItem label="工作时间">
          <NInput v-model:value="formModel.work_time" placeholder="如 09:00-18:00" />
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
          <NButton type="primary" :loading="saving" @click="handleSubmit">确定</NButton>
        </div>
      </template>
    </NModal>
  </div>
</template>

<style scoped></style>
