import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'overview',
      component: () => import('./views/OverviewView.vue'),
      meta: { title: '服务器总览' },
    },
    {
      path: '/board',
      name: 'board',
      component: () => import('./views/BoardView.vue'),
      meta: { title: '应用面板' },
    },
    {
      path: '/cards/:id',
      name: 'card-detail',
      component: () => import('./views/CardDetailView.vue'),
      meta: { title: '卡片详情' },
    },
    {
      path: '/providers',
      name: 'providers',
      component: () => import('./views/ProvidersView.vue'),
      meta: { title: '模型与通道' },
    },
    {
      path: '/system',
      name: 'system',
      component: () => import('./views/SystemView.vue'),
      meta: { title: '系统与审计' },
    },
  ],
})

export default router
