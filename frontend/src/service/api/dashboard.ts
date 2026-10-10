import { request } from '../request';

/**
 * 首页统计接口
 * 对接后端 GET /api/dashboard/home
 */

export interface HomeCards {
  total_orders: number;
  total_amount_fen: number;
  today_orders: number;
  today_amount_fen: number;
}

export interface HomeStat {
  label: string;
  value: string;
}

export interface HomeTrend {
  dates: string[];
  orders: number[];
  amounts: number[];
}

export interface HomeDistribution {
  name: string;
  value: number;
}

export interface HomeSummary {
  cards: HomeCards;
  stats: HomeStat[];
  trend: HomeTrend;
  distribution: HomeDistribution[];
}

/** 获取首页统计数据 */
export function fetchHomeSummary() {
  return request<HomeSummary>({
    url: '/api/dashboard/home',
    method: 'get'
  });
}
