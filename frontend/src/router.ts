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
      path: '/cards/:id/workspace',
      name: 'card-workspace',
      component: () => import('./views/CardWorkspaceView.vue'),
      meta: { title: '工作区' },
    },
    {
      path: '/cards/:id',
      name: 'card-detail',
      component: () => import('./views/CardDetailView.vue'),
      meta: { title: '卡片详情' },
    },
    {
      path: '/dsh',
      name: 'dsh',
      component: () => import('./views/DshView.vue'),
      meta: { title: 'dsh 工作区' },
    },
    {
      path: '/files',
      name: 'files',
      component: () => import('./views/FilesView.vue'),
      meta: { title: '服务器文件' },
    },
    {
      path: '/terminal',
      name: 'terminal',
      component: () => import('./views/TerminalView.vue'),
      meta: { title: '终端' },
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
