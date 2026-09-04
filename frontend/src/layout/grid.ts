/**
 * 计算卡片网格的列数，使最后一行尽量排满。
 *
 * 页面里多处是"N 张同构卡片"的网格。此前用 `repeat(auto-fit, minmax(…))`
 * 交给浏览器按可用宽度决定列数，结果 8 张卡排成 5+3、6 张排成 4+2，
 * 末行留一段空洞，整屏看上去参差。
 *
 * 列数不能写死：批次数、阶段数随快照数据变化（演示数据 8 个批次，
 * 现网只有 5 个），写死 4 列在 5 个批次时又会变成 4+1。
 * 因此按实际数量取一个能整除的列数。
 *
 * @param count      卡片数量
 * @param maxPerRow  单行最多容纳几张（受容器宽度和可读性限制）
 */
export function balancedColumns(count: number, maxPerRow = 5): number {
  if (count <= 0) return 1
  // 一行放得下就不换行
  if (count <= maxPerRow) return count

  // 优先取能整除的最大列数，这样每一行都是满的
  for (let cols = maxPerRow; cols >= 3; cols -= 1) {
    if (count % cols === 0) return cols
  }

  // 质数等无解的情况：对半分成两行，让两行长度尽量接近
  return count <= maxPerRow * 2 ? Math.ceil(count / 2) : maxPerRow
}

/** 生成可直接绑到 style 上的等宽列定义。 */
export function balancedGridStyle(count: number, maxPerRow = 5) {
  return { gridTemplateColumns: `repeat(${balancedColumns(count, maxPerRow)}, minmax(0, 1fr))` }
}
