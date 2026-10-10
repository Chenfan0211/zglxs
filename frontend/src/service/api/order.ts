import { request } from '../request';

/**
 * 订单业务模块接口
 * 对接后端 /apiv1/user/order/*（见 app/api/order.py）
 */

export interface OrderItem {
  provider_order_id: string;
  order_no: string;
  account_id: string | null;
  order_status: number | null;
  order_status_str?: string;
  pay_amount_fen: number | null;
  verify_amount?: number | null;
  create_order_time: number | null;
  update_order_time: number | null;
  pay_time: number | null;
  use_time?: string | null;
  subject_id: string | null;
  product_id: string | null;
  out_product_id?: string | null;
  product_name?: string | null;
  user_tel?: string | null;
  user_tel_end?: string | null;
  memo?: string | null;
  follow_status_str?: string | null;
  custom_department_name?: string | null;
  custom_service_group_name?: string | null;
  custom_cate_name?: string | null;
  custom_name?: string | null;
  department_name?: string | null;
  live_name?: string | null;
  anchor_name?: string | null;
  console_name?: string | null;
  maintenance_department_name?: string | null;
  maintenance_name?: string | null;
  refund_money?: number | null;
  refund_type_str?: string | null;
  add_price?: number | null;
  cost_amount?: number | null;
  profit_amount?: number | null;
}

export interface OrderFollow {
  id?: number;
  follow_status: string;
  owner_staff_id: number | null;
  follow_day: number | null;
  memo: string | null;
  tel: string | null;
  lock_flag: boolean;
}

export interface FollowLog {
  id: number;
  provider_order_id: string;
  staff_id: number | null;
  staff_name?: string;
  action: string;
  remark: string | null;
  created_at?: string | null;
}

export interface ClaimLog {
  id: number;
  provider_order_id: string;
  staff_id: number | null;
  status: string;
  created_at?: string | null;
}

interface ListResult<T> {
  total: number;
  list: T[];
}

export function fetchOrderList(params: Record<string, unknown> = {}) {
  return request<ListResult<OrderItem>>({ url: '/apiv1/user/order/tradelist', method: 'post', data: params });
}
export function fetchOrderDetail(order_id: string) {
  return request<OrderItem & { follow: OrderFollow | null }>({
    url: '/apiv1/user/order/detail',
    method: 'post',
    data: { order_id }
  });
}
export function updateFollow(data: Record<string, unknown>) {
  return request<OrderFollow>({ url: '/apiv1/user/order/updatefollowstatus', method: 'post', data });
}
export function claimOrder(order_id: string, staff_id?: number | null) {
  return request({ url: '/apiv1/user/order/claim', method: 'post', data: { order_id, staff_id } });
}
export function fetchFollowLogs(params: Record<string, unknown> = {}) {
  return request<ListResult<FollowLog>>({ url: '/apiv1/user/order/followlog', method: 'post', data: params });
}
export function fetchClaimLogs(params: Record<string, unknown> = {}) {
  return request<ListResult<ClaimLog>>({ url: '/apiv1/user/order/claimlog', method: 'post', data: params });
}
export function searchOrderStaff(role = '') {
  return request<{ list: { id: number; name: string; nickname: string }[] }>({
    url: '/apiv1/user/order/searchanchor',
    method: 'post',
    data: { role }
  });
}

// ---------- 跟单状态管理 ----------
export interface FollowStatus {
  id: number;
  name: string;
  sort_order: number;
  status: boolean;
  created_at?: string | null;
}
export function fetchFollowStatuses(params: Record<string, unknown> = {}) {
  return request<ListResult<FollowStatus>>({ url: '/apiv1/user/followstatus/index', method: 'post', data: params });
}
export function addFollowStatus(data: Record<string, unknown>) {
  return request<FollowStatus>({ url: '/apiv1/user/followstatus/add', method: 'post', data });
}
export function editFollowStatus(data: Record<string, unknown>) {
  return request<FollowStatus>({ url: '/apiv1/user/followstatus/edit', method: 'post', data });
}
export function delFollowStatus(id: number) {
  return request({ url: '/apiv1/user/followstatus/del', method: 'post', data: { id } });
}

// ---------- 订单子列表（核销/退款/预约/公海） ----------
export function fetchUseList(params: Record<string, unknown> = {}) {
  return request<ListResult<OrderItem>>({ url: '/apiv1/user/order/uselist', method: 'post', data: params });
}
export function fetchRefundList(params: Record<string, unknown> = {}) {
  return request<ListResult<OrderItem>>({ url: '/apiv1/user/order/refundlist', method: 'post', data: params });
}
export function fetchReservationList(params: Record<string, unknown> = {}) {
  return request<ListResult<OrderItem>>({ url: '/apiv1/user/order/reservationlist', method: 'post', data: params });
}
export function fetchClaimCustomList(params: Record<string, unknown> = {}) {
  return request<ListResult<OrderItem>>({ url: '/apiv1/user/order/claimcustomlist', method: 'post', data: params });
}
