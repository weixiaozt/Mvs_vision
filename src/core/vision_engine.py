"""
MVS Vision - 视觉引擎核心
基于 OpenCV 的真实图像处理与缺陷检测
"""
import cv2
import numpy as np
from typing import List, Dict


class VisionEngine:
    """
    图像处理流水线：
    1. 灰度转换
    2. 高斯滤波
    3. 阈值分割 / 边缘检测 / 形态学（可选）
    4. 轮廓检测 + 面积过滤
    5. 缺陷标注
    """

    def __init__(self):
        # 处理参数
        self.threshold_low = 50
        self.threshold_high = 200
        self.gaussian_kernel = 5
        self.min_defect_area = 100

        # 功能开关
        self.enable_binary = False
        self.enable_edge = True
        self.enable_morph = False

    def set_parameter(self, name: str, value):
        if hasattr(self, name):
            setattr(self, name, value)

    def process(self, image_rgb: np.ndarray) -> Dict:
        """
        处理单帧图像
        :param image_rgb: (H, W, 3) uint8 RGB 图像
        :return: {
            "ok": bool,
            "defects": [{"type", "x", "y", "w", "h", "score", "area"}],
            "processed_image": np.ndarray,  # RGB, 带标注
            "mask": np.ndarray,             # 二值掩码
            "gray": np.ndarray,             # 灰度图
        }
        """
        if image_rgb is None or image_rgb.size == 0:
            return {"ok": True, "defects": [], "processed_image": image_rgb, "mask": None, "gray": None}

        # 1. 灰度转换
        gray = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2GRAY)

        # 2. 高斯滤波
        proc = gray.copy()
        k = max(1, int(self.gaussian_kernel))
        if k % 2 == 0:
            k += 1
        if k > 1:
            proc = cv2.GaussianBlur(proc, (k, k), 0)

        mask = None
        defects = []

        # 3. 图像处理分支
        if self.enable_edge:
            # Canny 边缘检测
            edges = cv2.Canny(proc, self.threshold_low, self.threshold_high)
            if self.enable_morph:
                edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
            mask = edges
            defects = self._find_defects_from_mask(mask, image_rgb.shape[:2])

        elif self.enable_binary:
            # 阈值分割：在范围内为前景
            _, mask_low = cv2.threshold(proc, self.threshold_low, 255, cv2.THRESH_BINARY)
            _, mask_high = cv2.threshold(proc, self.threshold_high, 255, cv2.THRESH_BINARY_INV)
            mask = cv2.bitwise_and(mask_low, mask_high)
            if self.enable_morph:
                mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
                mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
            defects = self._find_defects_from_mask(mask, image_rgb.shape[:2])

        else:
            # 不做处理，直接输出原图
            mask = np.zeros_like(gray)

        # 4. 标注结果
        annotated = image_rgb.copy()
        ok = len(defects) == 0

        if not ok:
            for i, d in enumerate(defects):
                x, y, w, h = d["x"], d["y"], d["w"], d["h"]
                # 画红框
                cv2.rectangle(annotated, (x, y), (x + w, y + h), (255, 50, 50), 2)
                # 标签
                label = f"{d['type']} {d['score']:.2f}"
                (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
                cv2.rectangle(annotated, (x, y - th - 6), (x + tw + 4, y), (255, 50, 50), -1)
                cv2.putText(annotated, label, (x + 2, y - 3), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

        # 在左上角叠加信息
        info_lines = [
            f"Defects: {len(defects)}",
            f"Result: {'OK' if ok else 'NG'}",
        ]
        for idx, line in enumerate(info_lines):
            color = (50, 255, 50) if ok else (50, 50, 255)
            y_offset = 25 + idx * 22
            cv2.putText(annotated, line, (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

        return {
            "ok": ok,
            "defects": defects,
            "processed_image": annotated,
            "mask": mask,
            "gray": gray,
        }

    def _find_defects_from_mask(self, mask: np.ndarray, shape) -> List[Dict]:
        """从二值掩码中提取缺陷区域"""
        if mask is None:
            return []

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        defects = []

        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < self.min_defect_area:
                continue

            x, y, w, h = cv2.boundingRect(cnt)
            # 缺陷得分：面积归一化到 [0,1]，5000 px 及以上饱和
            score = min(0.99, area / 5000.0)

            # 根据宽高比分类缺陷类型
            aspect = max(w, 1) / max(h, 1)
            if aspect > 3 or aspect < 0.33:
                d_type = "划痕"
            elif area > 2000:
                d_type = "缺角"
            elif area > 500:
                d_type = "异物"
            else:
                d_type = "污点"

            defects.append({
                "type": d_type,
                "x": int(x),
                "y": int(y),
                "w": int(w),
                "h": int(h),
                "score": float(score),
                "area": int(area),
            })

        # 按面积从大到小排序
        defects.sort(key=lambda d: d["area"], reverse=True)
        return defects
