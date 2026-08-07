import { createRouter, createWebHistory } from 'vue-router';
import { isAuthenticated, initAuth } from '../stores/auth';

const routes = [
  { path: '/', redirect: '/dashboard' },
  { path: '/login', component: () => import('../views/LoginView.vue'), meta: { title: '登录', public: true } },
  { path: '/dashboard', component: () => import('../views/DashboardView.vue'), meta: { title: '总览大屏' } },
  { path: '/cabinet', component: () => import('../views/CabinetView.vue'), meta: { title: '工具箱状态' } },
  { path: '/records', component: () => import('../views/RecordsView.vue'), meta: { title: '借还记录' } },
  { path: '/alerts', component: () => import('../views/AlertsView.vue'), meta: { title: '异常告警' } },
  { path: '/inspections', component: () => import('../views/InspectionView.vue'), meta: { title: '工具损坏检测' } },
  { path: '/assistant', component: () => import('../views/AssistantView.vue'), meta: { title: '大模型助手' } }
];

const router = createRouter({
  history: createWebHistory(),
  routes
});

initAuth();

router.beforeEach((to, from, next) => {
  if (to.meta.public) {
    next();
    return;
  }
  if (!isAuthenticated.value) {
    next('/login');
    return;
  }
  next();
});

export default router;
