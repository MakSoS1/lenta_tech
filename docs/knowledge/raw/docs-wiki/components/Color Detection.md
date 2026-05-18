---
type: component
---
# Color Detection

HSV-based определение цвета ценника:
- Red: H 0-10 или 170-180
- Yellow: H 20-35
- Orange: H 10-20
- Default: "red"

**Текущая accuracy**: 54-72% (varies by video)
**Method**: Анализировать левую треть кропа (где цветная полоска), fallback на весь кроп если saturation < 50

**Двойная роль**:
1. Tag color classification (red/yellow/orange)
2. HSV detection fallback when YOLO finds no tags (see [[A21 Color Fallback]])

**Связи**: [[D1 HSV Detection]] → [[A21 Color Fallback]]
