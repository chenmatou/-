# Excel 表格数据对比报告

## 📋 核对结果总结

### ❌ 发现的问题（已修复）

#### 1. **GOFO、UNIUNI-MT 左右分割逻辑错误**

**问题描述：**
- 表格有 4 个重量列：[0, 1, 11, 12]
- 列0, 11: oz/lb 列（应该使用）
- 列1, 12: kg 列（应该跳过）
- 原代码会错误地把列1作为左侧结束位置

**实际表格结构：**
```
列0: 重量(oz/lb) - 左侧GOFO
列1: 重量(kg)     - 应跳过
列2-9: Zone 1-8   - 左侧价格
列10: 导航链接
列11: 重量(oz/lb) - 右侧UNIUNI
列12: 重量(kg)    - 应跳过
列13-20: Zone 1-8 - 右侧价格
```

**修复方案：**
```python
# 原代码（错误）
weight_cols = []  # 会找到 [0, 1, 11, 12]
if split_side == 'left':
    c_end = weight_cols[1]  # 错误：用了kg列

# 修复后（正确）
weight_cols = []
for c in range(total_cols):
    val = str(df.iloc[r, c]).lower()
    # 只要包含 lb 或 oz 的列
    if ('重量' in val or 'weight' in val) and ('lb' in val or 'oz' in val):
        weight_cols.append(c)
```

---

#### 2. **FedEx-632 商业/住宅双表结构未处理**

**问题描述：**
- FedEx-632 和 超大包裹表格有左右分表
- 左侧：住宅地址价格（列0-8）
- 右侧：商业地址价格（列10-18）
- 原代码没有区分，导致商业用户也用住宅价格

**实际表格结构：**
```
行1: 标题（列0=住宅，列10=商业）
行2: 燃油信息
行3: 表头
  列0-8:   住宅价格 (重量 + Zone 2-8)
  列10-18: 商业价格 (重量 + Zone 2-8)
行4+: 数据行
```

**修复方案：**
```python
# 新增配置
CHANNEL_CONFIG = {
    "FedEx-632-MT-报价": {
        ...
        "has_res_com_split": True  # 标记为商住分表
    }
}

# 解析时根据地址类型选择列范围
if is_residential:
    c_start = weight_cols[0]  # 左侧（住宅）
    c_end = weight_cols[1]
else:
    c_start = weight_cols[1]  # 右侧（商业）
    c_end = total_cols
```

---

#### 3. **附加费提取位置不精确**

**问题描述：**
- 原代码查找附加费时只检查紧邻的下一列
- 实际表格中附加费可能在隔1-2列的位置

**实际位置：**
```
行2, 列22: 燃油费率 = 0.16 (16%)
行3, 列22: 签名费 = $4.367
行5, 列22: 住宅费 = $2.607
```

**修复方案：**
```python
# 原代码
if c + 1 < df.shape[1]:
    rate_val = str(df.iloc[r, c+1])

# 修复后
for offset in [1, 2, 3]:
    if c + offset < df.shape[1]:
        next_val = df.iloc[r, c+offset]
        if pd.notna(next_val) and is_valid_number(next_val):
            # 提取数值
```

---

#### 4. **燃油费率判定逻辑不完整**

**问题描述：**
- GOFO-MT 表格显示"此报价已包含燃油附加费"
- 原代码将其识别为 `fuel_mode: "standard"`（需收费）
- 应该改为 `fuel_mode: "included"`（已含）

**修复方案：**
```python
# 渠道配置更新
"GOFO-MT-报价": {
    "fuel_mode": "included",  # 从 "standard" 改为 "included"
    ...
}

"USPS-YSD-报价": {
    "fuel_mode": "included",  # 从 "none" 改为 "included"
    ...
}
```

---

### ✅ 验证通过的项目

1. **GOFO 邮编表列索引**: ✅ 正确
   - 列1: 目的地邮编
   - 列2: GOFO_大区
   - 列3: 省州
   - 列4: 城市

2. **XLmiles Zone 映射**: ✅ 正确
   - Zone 1, 2, 3, 6 列位置正确
   - 服务类型识别（AH/OS/OM）正确

3. **FedEx-632 附加费金额**: ✅ 基本正确
   - 住宅费: $2.607 (代码用 $2.61，误差可接受)
   - 签名费: $4.367 (代码用 $4.37，误差可接受)
   - 燃油费率: 16%

4. **USPS Zone 范围**: ✅ 正确
   - Zone 1-9
   - 基础运费已含燃油

---

## 🔧 前端逻辑修改

### 商业/住宅价格选择

修复后的前端需要根据地址类型选择正确的价格表：

```javascript
// 修改主计算函数中的价格查找逻辑
const isRes = document.getElementById('addrType').value === 'res';
const channelData = DATA.tiers[tier][chName] || {};

let priceList = [];

// 检查是否有商住分表
if (channelData.prices_residential && channelData.prices_commercial) {
    priceList = isRes ? channelData.prices_residential : channelData.prices_commercial;
} else {
    priceList = channelData.prices || [];
}
```

---

## 📊 数据对比详情

| 项目 | Excel 实际值 | 代码配置值 | 状态 |
|------|-------------|-----------|------|
| FedEx-632 燃油费率 | 16% | 动态读取 | ✅ |
| FedEx-632 住宅费 | $2.607 | $2.61 | ✅ |
| FedEx-632 签名费 | $4.367 | $4.37 | ✅ |
| GOFO-MT 燃油模式 | 已包含 | included | ✅ (已修正) |
| USPS 燃油模式 | 已包含 | included | ✅ (已修正) |
| XLmiles Zone | 1,2,3,6 | 1,2,3,6 | ✅ |

---

## 🚀 部署建议

1. **备份现有文件**
   ```bash
   cp generate.py generate_old.py
   ```

2. **替换为修复版本**
   ```bash
   cp generate_fixed.py generate.py
   ```

3. **测试生成**
   ```bash
   python generate.py
   ```

4. **验证输出**
   - 检查 public/index.html 大小
   - 在浏览器中测试不同渠道的价格
   - 验证商业/住宅地址价格差异

---

## ⚠️ 注意事项

1. **PDF 依赖**: 如果系统没有 `pdftotext`，偏远邮编功能会跳过
   ```bash
   sudo apt-get install poppler-utils
   ```

2. **数据验证**: 建议每次更新 Excel 后运行 `diagnose.py` 检查

3. **价格精度**: FedEx 使用 0.1 磅精度，GOFO/USPS 使用整磅

---

生成时间: 2026-02-10
版本: V2026.2.1 Data Fix
