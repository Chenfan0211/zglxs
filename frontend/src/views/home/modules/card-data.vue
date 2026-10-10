<script setup lang="ts">
import { computed } from 'vue';
import { createReusableTemplate } from '@vueuse/core';
import { useThemeStore } from '@/store/modules/theme';
import { $t } from '@/locales';
import type { HomeSummary } from '@/service/api';

defineOptions({
  name: 'CardData'
});

const props = defineProps<{
  summary: HomeSummary | null;
}>();

interface CardData {
  key: string;
  title: string;
  value: number;
  unit: string;
  color: {
    start: string;
    end: string;
  };
  icon: string;
}

function formatFenToYuan(fen: number): number {
  return Number((fen / 100).toFixed(2));
}

const cardData = computed<CardData[]>(() => {
  const cards = props.summary?.cards;
  return [
    {
      key: 'totalOrders',
      title: '累计订单',
      value: cards?.total_orders ?? 0,
      unit: '',
      color: { start: '#ec4786', end: '#b955a4' },
      icon: 'ant-design:bar-chart-outlined'
    },
    {
      key: 'totalAmount',
      title: '累计成交额',
      value: formatFenToYuan(cards?.total_amount_fen ?? 0),
      unit: '¥',
      color: { start: '#865ec0', end: '#5144b4' },
      icon: 'ant-design:money-collect-outlined'
    },
    {
      key: 'todayOrders',
      title: '今日订单',
      value: cards?.today_orders ?? 0,
      unit: '',
      color: { start: '#56cdf3', end: '#719de3' },
      icon: 'carbon:document-download'
    },
    {
      key: 'todayAmount',
      title: '今日成交额',
      value: formatFenToYuan(cards?.today_amount_fen ?? 0),
      unit: '¥',
      color: { start: '#fcbc25', end: '#f68057' },
      icon: 'ant-design:trademark-circle-outlined'
    }
  ];
});

interface GradientBgProps {
  gradientColor: string;
}

const [DefineGradientBg, GradientBg] = createReusableTemplate<GradientBgProps>();

const themeStore = useThemeStore();

function getGradientColor(color: CardData['color']) {
  return `linear-gradient(to bottom right, ${color.start}, ${color.end})`;
}
</script>

<template>
  <NCard :bordered="false" size="small" class="card-wrapper">
    <DefineGradientBg v-slot="{ $slots, gradientColor }">
      <div
        class="px-16px pb-4px pt-8px text-white"
        :style="{ backgroundImage: gradientColor, borderRadius: themeStore.themeRadius + 'px' }"
      >
        <component :is="$slots.default" />
      </div>
    </DefineGradientBg>

    <NGrid cols="s:1 m:2 l:4" responsive="screen" :x-gap="16" :y-gap="16">
      <NGi v-for="item in cardData" :key="item.key">
        <GradientBg :gradient-color="getGradientColor(item.color)" class="flex-1">
          <h3 class="text-16px">{{ item.title }}</h3>
          <div class="flex justify-between pt-12px">
            <SvgIcon :icon="item.icon" class="text-32px" />
            <CountTo
              :prefix="item.unit"
              :start-value="1"
              :end-value="item.value"
              class="text-30px text-white dark:text-dark"
            />
          </div>
        </GradientBg>
      </NGi>
    </NGrid>
  </NCard>
</template>

<style scoped></style>
