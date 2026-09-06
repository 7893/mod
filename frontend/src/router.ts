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
    { path: '/', redirect: '/a' },
    {
      path: '/a',
      component: DashboardView,
      meta: { title: '项目总览', screen: 'A' },
    },
    {
      path: '/b',
      component: ConstructionView,
      meta: { title: '建设进度', screen: 'B' },
    },
    {
      path: '/c',
      component: RolloutView,
      meta: { title: '上线推广', screen: 'C' },
    },
    {
      path: '/d',
      component: InsightsView,
      meta: { title: '风险预警', screen: 'D' },
    },
    {
      path: '/e',
      component: IssuesView,
      meta: { title: '合规监督', screen: 'E' },
    },
    {
      path: '/f',
      component: OperationsView,
      meta: { title: '业务运营', screen: 'F' },
    },
    // 数据准备台账：内容待并入建设进度（B）后退役，暂保留路由不进导航（KI-029）
    {
      path: '/data',
      component: DataView,
      meta: { title: '项目台账', screen: 'legacy' },
    },
  ],
})
