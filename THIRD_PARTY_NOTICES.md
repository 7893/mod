# 第三方组件与数据来源声明 / Third-Party Notices

更新日期 / Updated: 2026-09-23  
状态 / Status: 现行 / Active  
适用范围 / Scope: MOD 仓库中随构建使用或分发的第三方组件与数据

MOD 的 [MIT License](LICENSE) 仅授权 MOD 自行创作并有权授权的内容。第三方内容仍受其各自条款约束。
本文件记录来源与项目使用边界，不替代上游许可文本，也不扩大 MOD 或上游授予的任何权利。

The MOD [MIT License](LICENSE) covers only content authored by MOD and licensable by the project. Third-party
content remains subject to its own terms. This file records provenance and project usage boundaries; it neither
replaces upstream license texts nor enlarges any rights granted by MOD or an upstream project.

## Apache ECharts

- 组件 / Component: `echarts@6.1.0`
- 许可证 / License: [Apache License 2.0](https://github.com/apache/echarts/blob/6.1.0/LICENSE)
- 上游 / Upstream: [Apache ECharts](https://github.com/apache/echarts)

随上游分发的 NOTICE 如下 / Upstream NOTICE:

> Apache ECharts  
> Copyright 2017-2026 The Apache Software Foundation  
> This product includes software developed at The Apache Software Foundation (https://www.apache.org/).

## 中国地图数据隔离策略 / China map data isolation policy

MOD 仓库、依赖锁及默认构建均不包含或自动下载中国地图几何数据。前端只有在部署者显式设置
`VITE_CHINA_MAP_GEOJSON_URL` 后，才会在运行时获取并校验 ECharts 兼容的 GeoJSON
`FeatureCollection`；未配置、请求失败或格式无效时，界面明确显示不可用状态，不使用隐藏兜底地图。

部署者提供的数据不属于 MOD 分发内容。部署者必须自行确认其来源、授权、行政区划现势性、地图审图要求、
发布渠道及司法辖区合规性。MOD 的加载能力不构成对任何外部地图数据的认可或许可保证，外部地图也不得被
视为测绘、行政区划或边界认定的权威依据。

The MOD repository, dependency lock, and default build neither contain nor automatically download China map
geometry. The frontend fetches and validates an ECharts-compatible GeoJSON `FeatureCollection` at runtime only
when a deployer explicitly sets `VITE_CHINA_MAP_GEOJSON_URL`. Missing, failed, or invalid sources produce an
explicit unavailable state rather than a hidden fallback map.

Deployment-provided data is not distributed by MOD. The deployer must independently verify its provenance,
authorization, current administrative boundaries, map-review requirements, distribution channel, and applicable
law. MOD's loading capability is not an endorsement or licensing warranty for external map data, which must not
be treated as an authoritative surveying, administrative-boundary, or border reference.

### 项目所有者研究部署所用地图 / Map used by the owner's research deployment

项目所有者明确决定，其独立运行的非商业学习研究部署继续使用历史地图文件：

- 包：`china-geojson@1.0.0`
- 上游：[antvis/china-geojson](https://github.com/antvis/china-geojson)
- 固定包完整性：`sha512-WclJXmqad7RJwEnQKivYgBC43eevZ+vHUzC1g6aGectHdVunPt3RYsYM5z33coGerpXBurkDNvrhNLc91OMoww==`
- 用途边界：项目所有者自有部署中的非商业学习研究展示

该包未声明许可证，且上游已归档并撤下地图数据。因此地图文件由项目所有者在部署环境中单独保管，
不进入 MOD 仓库、依赖锁、源码包或默认构建，也不随 MOD 的 MIT License 授权。其他部署者不得将上述
来源说明理解为再许可，仍须自行选择并核验其地图数据源。

At the project owner's explicit direction, the separately operated, non-commercial research deployment continues
to use the historical `china-geojson@1.0.0` map file from
[antvis/china-geojson](https://github.com/antvis/china-geojson), pinned by the integrity value above. The package
declares no license and its upstream has archived the repository and withdrawn the map data. The file is therefore
kept only in the owner's deployment environment: it is not committed, locked, packaged, or included in MOD's
default build, and MOD's MIT License does not grant rights to it. Other deployers must select and validate their own
map source rather than treating this provenance record as a sublicense.
