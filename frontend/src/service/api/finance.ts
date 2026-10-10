import { request } from '../request';

/**
 * 财务模块接口
 * 对接后端 /apiv1/financial/*（见 app/api/finance.py）
 */

export interface SettlementItem {
  provider_order_id: string;
  order_no: string;
  account_id: string | null;
  product_id: string | null;
  out_product_id?: string | null;
  product_name?: string | null;
  user_tel?: string | null;
  user_tel_end?: string | null;
  pay_time: number | null;
  verify_amount?: number | null;
  order_status: number | null;
  goods?: unknown;
  ledger_total?: unknown;
  pay?: unknown;
  pay_discount?: unknown;
  user_deliv_platform_subsidy?: unknown;
  user_deliv_merchant_subsidy?: unknown;
  total_merchant_platform_service?: unknown;
  talent_commission?: unknown;
  total_agent_merchant?: unknown;
  total_operation_agent?: unknown;
  actual_insured?: unknown;
  crafts_man?: unknown;
  certificate_code?: string | null;
  custom_department_name?: string | null;
  custom_service_group_name?: string | null;
  custom_cate_name?: string | null;
  custom_name?: string | null;
  department_name?: string | null;
  live_name?: string | null;
  anchor_name?: string | null;
  console_name?: string | null;
  sale_user_role_str?: string | null;
  sale_channel_str?: string | null;
  sale_user_name?: string | null;
  maintenance_department_name?: string | null;
  maintenance_name?: string | null;
  refund_type_str?: string | null;
  refund_money?: number | null;
  add_price?: number | null;
  cost_amount?: number | null;
  profit_amount?: number | null;
}

export interface FinanceStatistic {
  total_orders: number;
  paid_orders: number;
  total_amount_fen: number;
  status_list: { status: number; label: string; count: number; amount_fen: number }[];
}

export function fetchSettlementList(params: Record<string, unknown> = {}) {
  return request<{ total: number; list: SettlementItem[] }>({
    url: '/apiv1/financial/settlementlist',
    method: 'post',
    data: params
  });
}
export function fetchFinanceStatistic() {
  return request<FinanceStatistic>({ url: '/apiv1/financial/statistic', method: 'post', data: {} });
}
