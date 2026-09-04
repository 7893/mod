import { createRouter, createWebHistory } from 'vue-router'

const DashboardView = () => import('./views/DashboardView.vue')
const ConstructionView = () => import('./views/ConstructionView.vue')
const RolloutView = () => import('./views/RolloutView.vue')
const DataView = () => import('./views/DataView.vue')
const OperationsView = () => import('./views/OperationsView.vue')
const IssuesView = () => import('./views/IssuesView.vue')
const InsightsView = () => import('./views/InsightsView.vue')

export default createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    { path: '/', redirect: '/dashboard' },
    {
      path: '/dashboard',
      component: DashboardView,
      meta: { title: '项目总览', screen: 'A', code: 'A1-A8' },
    },
    {
      path: '/construction',
      component: ConstructionView,
      meta: { title: '建设进度', screen: 'B', code: 'B1-B5' },
    },
    {
      path: '/rollout',
      component: RolloutView,
      meta: { title: '上线推广', screen: 'C', code: 'C1-C6' },
    },
    {
      path: '/data',
      component: DataView,
      meta: { title: '项目台账', screen: 'G', code: 'G1-G3' },
    },
    {
      path: '/operations',
      component: OperationsView,
      meta: { title: '业务运营', screen: 'D', code: 'D1-D7' },
    },
    {
      path: '/issues',
      component: IssuesView,
      meta: { title: '问题清单', screen: 'E', code: 'E1-E5' },
    },
    {
      path: '/insights',
      component: InsightsView,
      meta: { title: '智能研判', screen: 'F', code: 'F1-F7' },
    },
  ],
})
