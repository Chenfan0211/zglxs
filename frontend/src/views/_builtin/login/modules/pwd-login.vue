<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue';
import { loginModuleRecord } from '@/constants/app';
import { fetchCaptcha } from '@/service/api';
import { useAuthStore } from '@/store/modules/auth';
import { useRouterPush } from '@/hooks/common/router';
import { useFormRules, useNaiveForm } from '@/hooks/common/form';
import { $t } from '@/locales';

defineOptions({
  name: 'PwdLogin'
});

const authStore = useAuthStore();
const { toggleLoginModule } = useRouterPush();
const { formRef, validate } = useNaiveForm();
const { defaultRequiredRule } = useFormRules();

interface FormModel {
  mobile: string;
  password: string;
  captcha: string;
}

const model: FormModel = reactive({
  mobile: '',
  password: '',
  captcha: ''
});

const captchaImage = ref('');
const captchaKey = ref('');

async function loadCaptcha() {
  const { data, error } = await fetchCaptcha();
  if (!error && data) {
    captchaImage.value = data.content;
    captchaKey.value = data.key;
  }
}

onMounted(() => {
  loadCaptcha();
});

// demo 账号可能是非手机号、验证码为 4 位，这里仅做必填校验
const rules = computed<Record<keyof FormModel, App.Global.FormRule[]>>(() => ({
  mobile: [defaultRequiredRule],
  password: [defaultRequiredRule],
  captcha: [defaultRequiredRule]
}));

async function handleSubmit() {
  await validate();
  await authStore.login(model.mobile, model.password, model.captcha, captchaKey.value);
}
</script>

<template>
  <NForm ref="formRef" :model="model" :rules="rules" size="large" :show-label="false" @keyup.enter="handleSubmit">
    <NFormItem path="mobile">
      <NInput v-model:value="model.mobile" :placeholder="$t('page.login.common.phonePlaceholder')" />
    </NFormItem>
    <NFormItem path="password">
      <NInput
        v-model:value="model.password"
        type="password"
        show-password-on="click"
        :placeholder="$t('page.login.common.passwordPlaceholder')"
      />
    </NFormItem>
    <NFormItem path="captcha">
      <div class="w-full flex-y-center gap-16px">
        <NInput v-model:value="model.captcha" :placeholder="$t('page.login.common.codePlaceholder')" />
        <div class="h-40px w-120px cursor-pointer shrink-0" @click="loadCaptcha">
          <img v-if="captchaImage" :src="captchaImage" alt="captcha" class="size-full rd-4px" />
          <div v-else class="size-full flex-center bg-#f3f6fb text-12px text-#999">验证码</div>
        </div>
      </div>
    </NFormItem>
    <NSpace vertical :size="24">
      <NButton type="primary" size="large" round block :loading="authStore.loginLoading" @click="handleSubmit">
        {{ $t('common.confirm') }}
      </NButton>
    </NSpace>
  </NForm>
</template>

<style scoped></style>
