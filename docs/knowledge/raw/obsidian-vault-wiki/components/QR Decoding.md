---
type: component
status: impossible
---
# QR Decoding

QR коды НЕ найдены ни одним декодером:
- pyzbar: 0 QR на всём видео
- zxing-cpp: 0 QR на всём видео (scan 299 frames)
- Проблема: QR коды на ценниках слишком малы (ценник 100-200px, QR ~20-30px)

**GT показывает**: QR содержит barcode, price1-4, wholesale levels
**Реальность**: QR в видео неразличим — пикселей недостаточно
**Урок**: Не полагаться на QR, извлекать данные из OCR/VLM
