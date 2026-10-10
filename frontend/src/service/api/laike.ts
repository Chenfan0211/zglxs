import { request } from '../request';

/**
 * 来客订单查询接口
 * 对接后端 /api/laike/*（见 app/api/laike_orders.py）
 */

export interface LaikeOrder {
  provider_order_id: string;
  account_id: string | null;
  order_status: number | null;
  pay_amount_fen: number | null;
  create_order_time: number | null;
  update_order_time: number | null;
  pay_time: number | null;
  subject_id: string | null;
  product_id: string | null;
  first_discovered_at: string | null;
  last_updated_at: string | null;
}

export interface LaikeOrderListResult {
  list: LaikeOrder[];
  total: number;
  page_num: number;
  page_size: number;
}

export interface LaikeOrderParams {
  account_id?: string;
  order_id?: string;
  order_status?: number;
  create_order_start_time?: number;
  create_order_end_time?: number;
  update_order_start_time?: number;
  update_order_end_time?: number;
  page_num?: number;
  page_size?: number;
}

/** 查询来客订单列表 */
export function fetchLaikeOrders(params: LaikeOrderParams) {
  return request<LaikeOrderListResult>({
    url: '/api/laike/orders',
    method: 'get',
    params
  });
}

/** 查询来客订单详情 */
export function fetchLaikeOrderDetail(orderId: string) {
  return request<LaikeOrder & { payload_json: unknown }>({
    url: `/api/laike/orders/${orderId}`,
    method: 'get'
  });
}
