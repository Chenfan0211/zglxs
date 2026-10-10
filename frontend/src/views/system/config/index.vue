<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue';
import { fetchSystemConfig, updateSystemConfig } from '@/service/api';

const loading = ref(false);
const saving = ref(false);

const form = reactive({
  web_name: '',
  logo: '',
  show_sale_user: false,
  show_live_room: false,
  order_auto_enter_day: null as number | null,
  order_no_release_status: '',
  live_view_cost: false
});

async function loadData() {
  loading.value = true;
  try {
    const { data, error } = await fetchSystemConfig();
    if (!error && data) {
      form.web_name = data.web_name || '';
      form.logo = data.logo || '';
      const c = data.config || {};
      form.show_sale_user = c.show_sale_user === '1' || c.show_sale_user === 'true';
      form.show_live_room = c.show_live_room === '1' || c.show_live_room === 'true';
      form.order_auto_enter_day = c.order_auto_enter_day ? Number(c.order_auto_enter_day) : null;
      form.order_no_release_status = c.order_no_release_status || '';
      form.live_view_cost = c.live_view_cost === '1' || c.live_view_cost === 'true';
    }
  } finally {
    loading.value = false;
  }
}

async function handleSave() {
  saving.value = true;
  try {
    const { error } = await updateSystemConfig({
      web_name: form.web_name,
      logo: form.logo,
      show_sale_user: form.show_sale_user ? '1' : '0',
      show_live_room: form.show_live_room ? '1' : '0',
      order_auto_enter_day: form.order_auto_enter_day ?? '',
      order_no_release_status: form.order_no_release_status,
      live_view_cost: form.live_view_cost ? '1' : '0'
    });
    if (error) return;
    window.$message?.success('保存成功');
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
    <NCard :bordered="false" title="系统配置" :loading="loading">
      <NForm label-placement="left" label-width="260" class="max-w-720px">
        <NFormItem label="系统名称">
          <NInput v-model:value="form.web_name" placeholder="请输入系统名称" />
        </NFormItem>
        <NFormItem label="Logo URL">
          <NInput v-model:value="form.logo" placeholder="Logo 图片地址" />
        </NFormItem>
        <NDivider title-placement="left">订单显示配置</NDivider>
        <NFormItem label="订单显示带货人">
          <NSwitch v-model:value="form.show_sale_user" />
        </NFormItem>
        <NFormItem label="订单显示所属直播间">
          <NSwitch v-model:value="form.show_live_room" />
        </NFormItem>
        <NFormItem label="订单自动释放到公海（天数）">
          <NInputNumber v-model:value="form.order_auto_enter_day" placeholder="订单自动释放到公海" clearable />
        </NFormItem>
        <NFormItem label="订单跟单状态锁定不释放到公海">
          <NInput v-model:value="form.order_no_release_status" placeholder="跟单状态，多个以逗号分隔" />
        </NFormItem>
        <NFormItem label="直播部门可查看订单成本/利润">
          <NSwitch v-model:value="form.live_view_cost" />
        </NFormItem>
        <div class="flex justify-end">
          <NButton type="primary" :loading="saving" @click="handleSave">保存</NButton>
        </div>
      </NForm>
    </NCard>
  </div>
</template>

<style scoped></style>
