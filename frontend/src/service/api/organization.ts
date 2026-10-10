import { request } from '../request';

/**
 * 组织模块接口（按老系统字段还原）
 * 对接后端 /apiv1/user/*（见 app/api/organization.py）
 */

export interface Department {
  id: number;
  name: string;
  department_name: string;
  dept_type: string;
  type: string;
  type_str: string;
  ordid: number;
  user_num?: number;
  remark?: string | null;
}

export interface Staff {
  id: number;
  name: string;
  nickname: string | null;
  mobile: string | null;
  department_id: number | null;
  department_name?: string;
  service_cate_id: string | null;
  role: string;
  role_str?: string;
  status: boolean;
}

export interface Account {
  id: number;
  username: string;
  account_name: string | null;
  account_id: string | null;
  check_msg: string | null;
  memo: string | null;
  product_num?: number;
  status_str?: string;
  status: boolean;
}

export interface Cate {
  id: number;
  name: string;
  status: boolean;
}

export interface Group {
  id: number;
  name: string;
  allocation_type: string | null;
  department_id: number | null;
  department_name?: string;
  web_hook: string | null;
  memo: string | null;
  ordid: number;
  status: boolean;
}

export interface GroupMember {
  id: number;
  group_id: number;
  staff_id: number;
  custom_uid: string | null;
  custom_name?: string;
  rate: number;
  day_limit_num: number | null;
  status: boolean;
  work_time: string | null;
}

export interface AccountProduct {
  id: number;
  account_id: number;
  product_id: string;
  out_product_id: string | null;
  product_name: string | null;
  sort_order: number;
}

interface ListResult<T> {
  total: number;
  list: T[];
}

// ---------- 部门 ----------
export function fetchDepartments(params: Record<string, unknown> = {}) {
  return request<ListResult<Department> & { department_type_list: { key: string; value: string }[] }>({
    url: '/apiv1/user/departments/index',
    method: 'post',
    data: params
  });
}
export function addDepartment(data: Record<string, unknown>) {
  return request<Department>({ url: '/apiv1/user/departments/add', method: 'post', data });
}
export function editDepartment(data: Record<string, unknown>) {
  return request<Department>({ url: '/apiv1/user/departments/edit', method: 'post', data });
}
export function delDepartment(id: number) {
  return request({ url: '/apiv1/user/departments/del', method: 'post', data: { id } });
}
export function searchDepartment(keyword = '') {
  return request<{ list: { id: number; department_name: string; type: string }[] }>({
    url: '/apiv1/user/departments/searchdepartment',
    method: 'post',
    data: { keyword }
  });
}

// ---------- 员工 ----------
export function fetchStaff(params: Record<string, unknown> = {}) {
  return request<ListResult<Staff>>({ url: '/apiv1/user/staff/index', method: 'post', data: params });
}
export function addStaff(data: Record<string, unknown>) {
  return request<Staff>({ url: '/apiv1/user/staff/add', method: 'post', data });
}
export function editStaff(data: Record<string, unknown>) {
  return request<Staff>({ url: '/apiv1/user/staff/edit', method: 'post', data });
}
export function delStaff(id: number) {
  return request({ url: '/apiv1/user/staff/del', method: 'post', data: { id } });
}

// ---------- 账号 ----------
export function fetchAccounts(params: Record<string, unknown> = {}) {
  return request<ListResult<Account>>({ url: '/apiv1/user/accounts/index', method: 'post', data: params });
}
export function addAccount(data: Record<string, unknown>) {
  return request<Account>({ url: '/apiv1/user/accounts/add', method: 'post', data });
}
export function editAccount(data: Record<string, unknown>) {
  return request<Account>({ url: '/apiv1/user/accounts/edit', method: 'post', data });
}
export function delAccount(id: number) {
  return request({ url: '/apiv1/user/accounts/del', method: 'post', data: { id } });
}
export function fetchAccountProducts(account_id: number) {
  return request<{ list: AccountProduct[] }>({
    url: '/apiv1/user/accounts/productlist',
    method: 'post',
    data: { account_id }
  });
}
export function addAccountProduct(data: Record<string, unknown>) {
  return request<AccountProduct>({ url: '/apiv1/user/accounts/productadd', method: 'post', data });
}
export function delAccountProduct(id: number) {
  return request({ url: '/apiv1/user/accounts/productdel', method: 'post', data: { id } });
}

// ---------- 客服分类 ----------
export function fetchCates(params: Record<string, unknown> = {}) {
  return request<ListResult<Cate>>({ url: '/apiv1/user/customservicecates/index', method: 'post', data: params });
}
export function addCate(data: Record<string, unknown>) {
  return request<Cate>({ url: '/apiv1/user/customservicecates/add', method: 'post', data });
}
export function editCate(data: Record<string, unknown>) {
  return request<Cate>({ url: '/apiv1/user/customservicecates/edit', method: 'post', data });
}
export function delCate(id: number) {
  return request({ url: '/apiv1/user/customservicecates/del', method: 'post', data: { id } });
}

// ---------- 客服组 ----------
export function fetchGroups(params: Record<string, unknown> = {}) {
  return request<ListResult<Group>>({ url: '/apiv1/user/customservicegroups/index', method: 'post', data: params });
}
export function addGroup(data: Record<string, unknown>) {
  return request<Group>({ url: '/apiv1/user/customservicegroups/add', method: 'post', data });
}
export function editGroup(data: Record<string, unknown>) {
  return request<Group>({ url: '/apiv1/user/customservicegroups/edit', method: 'post', data });
}
export function delGroup(id: number) {
  return request({ url: '/apiv1/user/customservicegroups/del', method: 'post', data: { id } });
}

// ---------- 客服组成员 ----------
export function fetchGroupMembers(params: Record<string, unknown> = {}) {
  return request<ListResult<GroupMember>>({
    url: '/apiv1/user/customservicegroupmembers/index',
    method: 'post',
    data: params
  });
}
export function addGroupMember(data: Record<string, unknown>) {
  return request<GroupMember>({ url: '/apiv1/user/customservicegroupmembers/add', method: 'post', data });
}
export function editGroupMember(data: Record<string, unknown>) {
  return request<GroupMember>({ url: '/apiv1/user/customservicegroupmembers/edit', method: 'post', data });
}
export function delGroupMember(id: number) {
  return request({ url: '/apiv1/user/customservicegroupmembers/del', method: 'post', data: { id } });
}
