import { computed, reactive, ref } from 'vue';
import { useRoute } from 'vue-router';
import { defineStore } from 'pinia';
import { useLoading } from '@sa/hooks';
import { fetchLogin } from '@/service/api';
import { useRouterPush } from '@/hooks/common/router';
import { localStg } from '@/utils/storage';
import { SetupStoreId } from '@/enum';
import { $t } from '@/locales';
import { useRouteStore } from '../route';
import { useTabStore } from '../tab';
import { clearAuthStorage, getToken } from './shared';

export const useAuthStore = defineStore(SetupStoreId.Auth, () => {
  const route = useRoute();
  const authStore = useAuthStore();
  const routeStore = useRouteStore();
  const tabStore = useTabStore();
  const { toLogin, redirectFromLogin } = useRouterPush(false);
  const { loading: loginLoading, startLoading, endLoading } = useLoading();

  const token = ref('');

  const userInfo: Api.Auth.UserInfo = reactive({
    userId: '',
    userName: '',
    mobile: '',
    nickname: '',
    roles: [],
    buttons: []
  });

  /** is super role in static route */
  const isStaticSuper = computed(() => {
    const { VITE_AUTH_ROUTE_MODE, VITE_STATIC_SUPER_ROLE } = import.meta.env;

    return VITE_AUTH_ROUTE_MODE === 'static' && userInfo.roles.includes(VITE_STATIC_SUPER_ROLE);
  });

  /** Is login */
  const isLogin = computed(() => Boolean(token.value));

  /** Reset auth store */
  async function resetStore() {
    recordUserId();

    clearAuthStorage();

    authStore.$reset();

    if (!route.meta.constant) {
      await toLogin();
    }

    tabStore.cacheTabs();
    routeStore.resetStore();
  }

  /** Record the user ID of the previous login session Used to compare with the current user ID on next login */
  function recordUserId() {
    if (!userInfo.userId) {
      return;
    }

    // Store current user ID locally for next login comparison
    localStg.set('lastLoginUserId', userInfo.userId);
  }

  /**
   * Check if current login user is different from previous login user If different, clear all tabs
   *
   * @returns {boolean} Whether to clear all tabs
   */
  function checkTabClear(): boolean {
    if (!userInfo.userId) {
      return false;
    }

    const lastLoginUserId = localStg.get('lastLoginUserId');

    // Clear all tabs if current user is different from previous user
    if (!lastLoginUserId || lastLoginUserId !== userInfo.userId) {
      localStg.remove('globalTabs');
      tabStore.clearTabs();

      localStg.remove('lastLoginUserId');
      return true;
    }

    localStg.remove('lastLoginUserId');
    return false;
  }

  /**
   * 解析后端返回的 auth_info（JSON 字符串）为用户信息
   */
  function applyAuthInfo(authInfoJson: string | undefined) {
    if (!authInfoJson) {
      return;
    }

    let raw: Record<string, unknown> | null = null;
    try {
      raw = JSON.parse(authInfoJson);
    } catch {
      // ignore malformed auth_info
    }

    if (!raw) {
      return;
    }

    const privCodes = Array.isArray(raw.menuPrivCodes)
      ? (raw.menuPrivCodes as Array<{ privCode?: string }>)
          .map(item => item.privCode)
          .filter((code): code is string => Boolean(code))
      : [];

    userInfo.userId = String(raw.user_id ?? raw.id ?? '');
    userInfo.userName = String(raw.nickname ?? raw.mobile ?? userInfo.userId);
    userInfo.mobile = raw.mobile ? String(raw.mobile) : '';
    userInfo.nickname = raw.nickname ? String(raw.nickname) : '';
    userInfo.roles = privCodes;
    userInfo.buttons = privCodes;
  }

  /**
   * Login
   *
   * @param mobile 账号（手机号）
   * @param password 密码
   * @param captcha 验证码
   * @param captchaKey 验证码 key
   * @param [redirect=true] Whether to redirect after login. Default is `true`
   */
  async function login(mobile: string, password: string, captcha: string, captchaKey: string, redirect = true) {
    startLoading();

    const { data: loginToken, error } = await fetchLogin(mobile, password, captcha, captchaKey);

    if (!error) {
      const pass = await loginByToken(loginToken);

      if (pass) {
        // Check if the tab needs to be cleared
        const isClear = checkTabClear();
        let needRedirect = redirect;

        if (isClear) {
          // If the tab needs to be cleared,it means we don't need to redirect.
          needRedirect = false;
        }
        await redirectFromLogin(needRedirect);

        window.$notification?.success({
          title: $t('page.login.common.loginSuccess'),
          content: $t('page.login.common.welcomeBack', { userName: userInfo.userName }),
          duration: 4500
        });
      }
    } else {
      resetStore();
    }

    endLoading();
  }

  async function loginByToken(loginToken: Api.Auth.LoginToken) {
    // 1. stored in the localStorage, the later requests need it in headers
    localStg.set('token', loginToken.token);

    // 2. 后端无独立 getUserInfo 接口，用户信息随登录返回在 auth_info 中
    applyAuthInfo(loginToken.auth_info);

    if (userInfo.userId) {
      token.value = loginToken.token;
      return true;
    }

    return false;
  }

  async function initUserInfo() {
    const maybeToken = getToken();

    if (maybeToken) {
      token.value = maybeToken;
      // 后端无 getUserInfo 接口，直接信任本地 token；用户信息由 login 时写入
    }
  }

  return {
    token,
    userInfo,
    isStaticSuper,
    isLogin,
    loginLoading,
    resetStore,
    login,
    initUserInfo
  };
});
