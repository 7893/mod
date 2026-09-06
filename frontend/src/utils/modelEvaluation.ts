/**
 * Model Evaluation Decision Utilities (KI-023 / KI-028 / KI-034 ADR-0010)
 *
 * 严守模型诚实展示契约：
 * 1. 回归模型 (R²)：只有独立测试集 R² > 0 时才判定为有效正向拟合 (regEffective)；
 *    当前测试集 R² <= 0 时按规范如实标记为验证未达标。
 * 2. 分类模型 (Accuracy)：泛化准确率落在 (0.5, 1.0) 开区间内时判定为有效 (clsEffective)；
 *    若准确率 <= 0.5（盲猜水平）或退化为 1.0（标签过度可分/特征泄露），标记为未达标。
 * 3. 整体就绪 (isReady)：后端标记为 READY 且至少有一个有效模型。
 */

export function isRegressionEffective(quality: number | null | undefined): boolean {
  return quality != null && Number.isFinite(quality) && quality > 0
}

export function isClassifierEffective(quality: number | null | undefined): boolean {
  return quality != null && Number.isFinite(quality) && quality > 0.5 && quality < 1.0
}

export function isAutomlReady(
  automlStatus: string | null | undefined,
  regQuality: number | null | undefined,
  clsQuality: number | null | undefined
): boolean {
  const isStatusReady = automlStatus === 'READY'
  const hasEffectiveModel = isRegressionEffective(regQuality) || isClassifierEffective(clsQuality)
  return isStatusReady && hasEffectiveModel
}
