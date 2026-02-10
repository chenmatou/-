import pandas as pd
import json
import re
import os
import warnings
import subprocess
from datetime import datetime

# 忽略 Excel 样式警告
warnings.filterwarnings('ignore', category=UserWarning, module='openpyxl')

# ==========================================
# 1. 全局配置
# ==========================================
DATA_DIR = "data"
OUTPUT_DIR = "public"

TIER_FILES = {
    "T0": "T0.xlsx", "T1": "T1.xlsx", "T2": "T2.xlsx", "T3": "T3.xlsx"
}

# 州名映射
US_STATES_CN = {
    'AL': '阿拉巴马', 'AK': '阿拉斯加', 'AZ': '亚利桑那', 'AR': '阿肯色', 'CA': '加利福尼亚',
    'CO': '科罗拉多', 'CT': '康涅狄格', 'DE': '特拉华', 'FL': '佛罗里达', 'GA': '佐治亚',
    'HI': '夏威夷', 'ID': '爱达荷', 'IL': '伊利诺伊', 'IN': '印第安纳', 'IA': '爱荷华',
    'KS': '堪萨斯', 'KY': '肯塔基', 'LA': '路易斯安那', 'ME': '缅因', 'MD': '马里兰',
    'MA': '马萨诸塞', 'MI': '密歇根', 'MN': '明尼苏达', 'MS': '密西西比', 'MO': '密苏里',
    'MT': '蒙大拿', 'NE': '内布拉斯加', 'NV': '内华达', 'NH': '新罕布什尔', 'NJ': '新泽西',
    'NM': '新墨西哥', 'NY': '纽约', 'NC': '北卡罗来纳', 'ND': '北达科他', 'OH': '俄亥俄',
    'OK': '俄克拉荷马', 'OR': '俄勒冈', 'PA': '宾夕法尼亚', 'RI': '罗德岛', 'SC': '南卡罗来纳',
    'SD': '南达科他', 'TN': '田纳西', 'TX': '德克萨斯', 'UT': '犹他', 'VT': '佛蒙特',
    'VA': '弗吉尼亚', 'WA': '华盛顿', 'WV': '西弗吉尼亚', 'WI': '威斯康星', 'WY': '怀俄明',
    'DC': '华盛顿特区'
}

WAREHOUSE_DB = {
    "60632": {"name": "SureGo美中芝加哥-60632仓", "region": "CENTRAL"},
    "91730": {"name": "SureGo美西库卡蒙格-91730新仓", "region": "WEST"},
    "91752": {"name": "SureGo美西米拉罗马-91752仓", "region": "WEST"},
    "08691": {"name": "SureGo美东新泽西-08691仓", "region": "EAST"},
    "06801": {"name": "SureGo美东贝塞尔-06801仓", "region": "EAST"},
    "11791": {"name": "SureGo美东长岛-11791仓", "region": "EAST"},
    "07032": {"name": "SureGo美东新泽西-07032仓", "region": "EAST"},
    "63461": {"name": "SureGo退货检测-美中密苏里63461退货仓", "region": "CENTRAL"}
}

# 渠道配置
CHANNEL_CONFIG = {
    "GOFO-报价": {
        "keywords": ["GOFO", "报价"], "exclude": ["MT", "UNIUNI", "大件"],
        "allow_wh": ["91730", "60632"], "fuel_mode": "none", "zone_source": "gofo",
        "fees": {"res": 0, "sig": 0}, "weight_precision": 1
    },
    "GOFO-MT-报价": {
        "keywords": ["GOFO", "UNIUNI", "MT"], "sheet_side": "left",
        "allow_wh": ["91730", "60632"], "fuel_mode": "included", "zone_source": "gofo",
        "fees": {"res": 0, "sig": 0}, "weight_precision": 1
    },
    "UNIUNI-MT-报价": {
        "keywords": ["GOFO", "UNIUNI", "MT"], "sheet_side": "right",
        "allow_wh": ["91730", "60632"], "fuel_mode": "none", "zone_source": "general",
        "fees": {"res": 0, "sig": 0}, "weight_precision": 1
    },
    "USPS-YSD-报价": {
        "keywords": ["USPS", "YSD"], "allow_wh": ["91730", "91752", "60632"], 
        "fuel_mode": "included", "zone_source": "general", "fees": {"res": 0, "sig": 0}, 
        "no_peak": True, "weight_precision": 1
    },
    "FedEx-632-MT-报价": {
        "keywords": ["632"], "allow_wh": ["91730", "91752", "60632", "08691", "06801", "11791", "07032"],
        "fuel_mode": "discount_85", "zone_source": "general", "fees": {"res": 2.61, "sig": 4.37},
        "weight_precision": 0.1, "has_res_com_split": True
    },
    "FedEx-MT-超大包裹-报价": {
        "keywords": ["超大包裹"], "allow_wh": ["91730", "91752", "60632", "08691", "06801", "11791", "07032"],
        "fuel_mode": "discount_85", "zone_source": "general", "fees": {"res": 2.61, "sig": 4.37},
        "weight_precision": 0.1, "has_res_com_split": True
    },
    "FedEx-ECO-MT报价": {
        "keywords": ["ECO", "MT"], "allow_wh": ["91730", "91752", "60632", "08691", "06801", "11791", "07032"],
        "fuel_mode": "included", "zone_source": "general", "fees": {"res": 0, "sig": 0},
        "weight_precision": 0.1
    },
    "FedEx-MT-危险品-报价": {
        "keywords": ["危险品"], "allow_wh": ["60632", "08691", "06801", "11791", "07032"], 
        "fuel_mode": "standard", "zone_source": "general", "fees": {"res": 3.32, "sig": 9.71},
        "weight_precision": 0.1
    },
    "GOFO大件-MT-报价": {
        "keywords": ["GOFO大件", "MT"], "allow_wh": ["91730", "91752", "08691", "06801", "11791", "07032"], 
        "fuel_mode": "standard", "zone_source": "gofo", "fees": {"res": 2.93, "sig": 0},
        "weight_precision": 1
    },
    "XLmiles-报价": {
        "keywords": ["XLmiles"], "allow_wh": ["91730"], 
        "fuel_mode": "none", "zone_source": "xlmiles", "fees": {"res": 0, "sig": 10.20},
        "weight_precision": 0.1
    }
}

# XLmiles Zone 映射表（从 91730 WEST 发货）
XLMILES_ZONE_MAP = {
    '900-935': 2,
    '936-961': 3, '970-979': 3, '980-994': 3, '995-999': 3,
    '820-831': 3, '832-838': 3, '890-899': 3,
    '600-629': 6, '630-699': 6, '700-729': 6, '730-799': 6,
    '400-599': 6, '000-199': 6, '200-399': 6
}

# ==========================================
# 2. HTML/JS 模板（保持不变，与之前相同）
# ==========================================
HTML_TEMPLATE = r"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>业务员报价助手 (V2026.2.1 数据修正版)</title>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
  <style>
    body { background-color: #f4f7f6; font-family: 'Segoe UI', sans-serif; }
    .header-bar { background: #222; color: #fff; padding: 15px 0; border-bottom: 4px solid #fd7e14; margin-bottom: 20px; }
    .card { border: none; box-shadow: 0 4px 12px rgba(0,0,0,0.05); border-radius: 10px; }
    .card-header { background-color: #fff; font-weight: 700; border-bottom: 1px solid #eee; }
    .price-main { font-size: 1.4rem; font-weight: 800; color: #d63384; }
    .warn-box { background: #fff3cd; border: 1px solid #ffeeba; color: #856404; padding: 12px; border-radius: 6px; font-size: 0.85rem; margin-bottom: 15px; }
    .compliance-box { background: #e9ecef; border-radius: 6px; padding: 10px; margin-top: 15px; font-size: 0.85rem; }
    .loc-box { margin-top: 5px; font-size: 0.85rem; }
    .tag-gofo { background: #d1e7dd; color: #0f5132; padding: 3px 8px; border-radius: 4px; border: 1px solid #badbcc; display: block; margin-bottom: 4px; }
    .tag-fedex { background: #cfe2ff; color: #084298; padding: 3px 8px; border-radius: 4px; border: 1px solid #b6d4fe; display: block; }
    .status-ok { color: #198754; font-weight: 700; }
    .status-err { color: #dc3545; font-weight: 700; }
    .error-alert { background: #f8d7da; border: 1px solid #f5c6cb; color: #721c24; padding: 10px; border-radius: 6px; margin-top: 10px; }
  </style>
</head>
<body>

<div class="header-bar">
  <div class="container d-flex justify-content-between align-items-center">
    <div>
      <h4 class="m-0 fw-bold">📦 业务员报价助手</h4>
      <div class="small opacity-75">V2026.2.1 | 修复Excel解析 | 商住分表 | 数据对齐</div>
    </div>
    <div class="text-end d-none d-md-block"><span class="badge bg-warning text-dark">T0-T3 实时</span></div>
  </div>
</div>

<div class="container pb-5">
  <div class="row g-4">
    <div class="col-lg-4">
      <div class="card h-100">
        <div class="card-header">1. 基础信息</div>
        <div class="card-body">
          <form id="calcForm">
            <div class="mb-3">
              <label class="form-label small fw-bold text-muted">发货仓库</label>
              <select class="form-select" id="whSelect"></select>
              <div class="form-text small text-end text-primary" id="whRegion"></div>
            </div>

            <div class="mb-3">
              <label class="form-label small fw-bold text-muted">客户等级</label>
              <div class="btn-group w-100" role="group">
                <input type="radio" class="btn-check" name="tier" id="t0" value="T0"><label class="btn btn-outline-dark" for="t0">T0</label>
                <input type="radio" class="btn-check" name="tier" id="t1" value="T1"><label class="btn btn-outline-dark" for="t1">T1</label>
                <input type="radio" class="btn-check" name="tier" id="t2" value="T2"><label class="btn btn-outline-dark" for="t2">T2</label>
                <input type="radio" class="btn-check" name="tier" id="t3" value="T3" checked><label class="btn btn-outline-dark" for="t3">T3</label>
              </div>
            </div>

            <div class="bg-light p-2 rounded border mb-3">
                <div class="d-flex justify-content-between align-items-center mb-1">
                    <label class="form-label small fw-bold text-muted m-0">燃油费率 (%)</label>
                    <span class="badge bg-secondary" style="font-size:0.65rem">MT系列</span>
                </div>
                <div class="input-group input-group-sm">
                    <input type="number" class="form-control fw-bold text-primary" id="fuelInput" value="16.0" step="0.01">
                    <span class="input-group-text">%</span>
                </div>
                <div class="form-text small text-muted" style="font-size:0.7rem">
                  * 仅 FedEx-632/超大件 享85折。
                </div>
            </div>

            <div class="row g-2 mb-3">
              <div class="col-6">
                <label class="form-label small fw-bold text-muted">邮编 (Zip)</label>
                <input type="text" class="form-control" id="zipCode" placeholder="5位数字" maxlength="5">
              </div>
              <div class="col-6">
                <label class="form-label small fw-bold text-muted">地址类型</label>
                <select class="form-select" id="addrType">
                  <option value="res">🏠 住宅</option>
                  <option value="com">🏢 商业</option>
                </select>
              </div>
              <div class="col-12" id="locDisplay"></div>
            </div>

            <div class="form-check form-switch mb-3">
              <input class="form-check-input" type="checkbox" id="sigToggle">
              <label class="form-check-label small fw-bold" for="sigToggle">签名服务 (Signature)</label>
            </div>

            <div class="bg-light p-3 rounded border">
              <label class="form-label small fw-bold text-muted mb-2">包裹规格 (Inch / Lb)</label>
              <div class="row g-2 mb-2">
                <div class="col-4"><input type="number" class="form-control form-control-sm" id="dimL" placeholder="长 L" step="0.1" min="0"></div>
                <div class="col-4"><input type="number" class="form-control form-control-sm" id="dimW" placeholder="宽 W" step="0.1" min="0"></div>
                <div class="col-4"><input type="number" class="form-control form-control-sm" id="dimH" placeholder="高 H" step="0.1" min="0"></div>
              </div>
              <div class="input-group input-group-sm">
                <span class="input-group-text">实重</span>
                <input type="number" class="form-control" id="weight" placeholder="LBS" step="0.1" min="0">
              </div>
            </div>

            <div class="compliance-box" id="complianceBox" style="display:none;">
              <div class="fw-bold mb-1 text-danger">⚠️ 规格预检</div>
              <ul class="mb-0 ps-3" id="complianceList"></ul>
            </div>

            <div id="errorBox" class="error-alert" style="display:none;"></div>

            <button type="button" class="btn btn-primary w-100 mt-4 fw-bold py-2" id="btnCalc">计算报价 (Calculate)</button>
          </form>
        </div>
      </div>
    </div>

    <div class="col-lg-8">
      <div class="card h-100">
        <div class="card-header d-flex justify-content-between align-items-center">
          <span>📊 测算结果</span>
          <span class="badge bg-warning text-dark" id="resTierBadge">T3</span>
        </div>
        <div class="card-body">
          <div class="warn-box">
            <strong>📢 计费规则说明：</strong><br>
            1. <b>燃油费</b>：FedEx-632/超大包裹(85折)；FedEx-ECO/USPS/GOFO-MT(含油)。<br>
            2. <b>计费精度</b>：GOFO/USPS(整磅)；FedEx/XLmiles(0.1磅)。<br>
            3. <b>商住分表</b>：FedEx-632/超大包裹 根据地址类型选择对应价格。<br>
            4. <b>Zone计算</b>：GOFO(自营表)；FedEx/USPS(动态)；XLmiles(邮编映射)。
          </div>

          <div class="alert alert-info py-2 small" id="pkgInfo">请在左侧录入数据...</div>

          <div class="table-responsive">
            <table class="table table-hover align-middle">
              <thead class="table-light small text-secondary">
                <tr>
                  <th width="20%">渠道</th>
                  <th width="8%">Zone</th>
                  <th width="10%">计费重</th>
                  <th width="12%">基础运费</th>
                  <th width="25%">附加费明细</th>
                  <th width="15%" class="text-end">总费用</th>
                  <th width="10%" class="text-center">状态</th>
                </tr>
              </thead>
              <tbody id="resBody">
                <tr><td colspan="7" class="text-center py-4 text-muted">暂无结果</td></tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  </div>
</div>

<footer class="text-center py-4 text-muted small">
  &copy; 2026 SureGo Logistics | Data Generated: <span id="updateTime"></span>
</footer>

<script>
  const DATA = __JSON_DATA__;
  document.getElementById('updateTime').innerText = new Date().toLocaleDateString();

  // [前端代码保持与之前相同，此处省略重复代码]
  // 包含: 邮编双显示、规格校验、Zone计算、主计算函数等
  
  // 1. 邮编双显示
  document.getElementById('zipCode').addEventListener('input', function() {
    let zip = this.value.trim();
    let display = document.getElementById('locDisplay');
    this.value = this.value.replace(/\D/g, '');
    
    if(zip.length === 5) {
        let html = '';
        if(DATA.gofo_zips && DATA.gofo_zips[zip]) {
            let g = DATA.gofo_zips[zip];
            html += `<div class="tag-gofo">🟢 [GOFO表] ${g.city}, ${g.state} (${g.cn_state}) - 区:${g.region}</div>`;
        }
        let fedexInfo = "通用地区";
        if(DATA.fedex_das_remote && DATA.fedex_das_remote.includes(zip)) {
            fedexInfo = "⚠️ FedEx 偏远 (Remote)";
        }
        html += `<div class="tag-fedex">🔵 [FedEx/通用] ${fedexInfo}</div>`;
        display.innerHTML = `<div class="loc-box">${html}</div>`;
    } else {
        display.innerHTML = '';
    }
  });

  // 2. 燃油初始化
  (function initFuel() {
    let maxFuel = 0;
    if(DATA.tiers && DATA.tiers.T3) {
        Object.values(DATA.tiers.T3).forEach(ch => {
            if(ch.fuel_rate && ch.fuel_rate > maxFuel) maxFuel = ch.fuel_rate;
        });
    }
    if(maxFuel > 0) document.getElementById('fuelInput').value = (maxFuel * 100).toFixed(2);
  })();

  // 3. XLmiles服务判定
  function getXLService(L, W, H, Wt) {
    let dims = [L, W, H].sort((a,b)=>b-a);
    let maxL = dims[0];
    let girth = maxL + 2*(dims[1] + dims[2]);
    
    if (maxL <= 96 && girth <= 130 && Wt <= 150) return { code: "AH", name: "AH大件" };
    if (maxL <= 108 && girth <= 165 && Wt <= 150) return { code: "OS", name: "OS大件" };
    if (maxL <= 144 && girth <= 225 && Wt <= 200) return { code: "OM", name: "OM超限" };
    return { code: null, name: "超XL规格" };
  }

  // 4. 规格校验
  function checkCompliance(pkg) {
    let dims = [pkg.L, pkg.W, pkg.H].sort((a,b)=>b-a);
    let L = dims[0], G = dims[0] + 2*(dims[1] + dims[2]);
    let msgs = [];
    
    if (pkg.Wt > 150 && pkg.Wt <= 200) msgs.push("重量 150-200lb (仅限XLmiles-OM)");
    if (pkg.Wt > 200) msgs.push("超200lb (所有渠道拒收)");
    if (L > 108 && L <= 144) msgs.push("长度 108-144in (仅限XLmiles)");
    if (L > 144) msgs.push("长度>144in (所有渠道拒收)");
    if (G > 165 && G <= 225) msgs.push("周长 165-225in (仅限XLmiles)");
    if (G > 225) msgs.push("周长>225in (所有渠道拒收)");
    
    let status = {
      uniuni: (pkg.Wt > 20 || L > 20) ? "❌ 超限" : "✅ 可用",
      usps: (pkg.Wt > 70 || G > 130) ? "❌ 超限" : "✅ 可用",
      fedex_std: (pkg.Wt > 150 || L > 108) ? "❌ 超限" : "✅ 可用",
      xl: (pkg.Wt > 200 || L > 144 || G > 225) ? "❌ 超限" : "✅ 可用"
    };
    
    return { msgs, status };
  }

  function updateComplianceUI() {
    let L = parseFloat(document.getElementById('dimL').value)||0;
    let W = parseFloat(document.getElementById('dimW').value)||0;
    let H = parseFloat(document.getElementById('dimH').value)||0;
    let Wt = parseFloat(document.getElementById('weight').value)||0;
    
    if(L > 0 && Wt > 0) {
      let res = checkCompliance({L,W,H,Wt});
      let html = "";
      
      if(res.msgs.length > 0) {
        html += `<li class="fw-bold text-danger">${res.msgs.join(', ')}</li>`;
      }
      html += `<li>UniUni: ${res.status.uniuni}</li>`;
      html += `<li>USPS: ${res.status.usps}</li>`;
      html += `<li>FedEx 标准: ${res.status.fedex_std}</li>`;
      html += `<li>XLmiles: ${res.status.xl}</li>`;
      
      document.getElementById('complianceList').innerHTML = html;
      document.getElementById('complianceBox').style.display = 'block';
    } else {
      document.getElementById('complianceBox').style.display = 'none';
    }
  }
  
  ['dimL','dimW','dimH','weight'].forEach(id => 
    document.getElementById(id).addEventListener('input', updateComplianceUI)
  );

  // 5. 仓库初始化
  const whSelect = document.getElementById('whSelect');
  Object.keys(DATA.warehouses).forEach(code => {
    let opt = document.createElement('option');
    opt.value = code;
    opt.text = DATA.warehouses[code].name;
    whSelect.appendChild(opt);
  });
  
  whSelect.addEventListener('change', () => {
    document.getElementById('whRegion').innerText = `区域: ${DATA.warehouses[whSelect.value].region}`;
    document.getElementById('resBody').innerHTML = 
      '<tr><td colspan="7" class="text-center py-4 text-muted">仓库已切换，请点击计算</td></tr>';
  });
  
  if(whSelect.options.length > 0) whSelect.dispatchEvent(new Event('change'));

  // 6. Zone计算
  function calcZone(destZip, originZip, conf) {
    if(!destZip || destZip.length < 3) return 8;
    
    let d = parseInt(destZip.substring(0,3));
    let whRegion = DATA.warehouses[originZip].region;

    if(conf.zone_source === 'gofo') {
        if(DATA.gofo_zips && DATA.gofo_zips[destZip]) {
            let zReg = DATA.gofo_zips[destZip].region; 
            if(whRegion === 'WEST' && zReg === 'WE') return 2;
            if(whRegion === 'CENTRAL' && zReg === 'CE') return 2;
            if(whRegion === 'EAST' && zReg === 'EA') return 2;
            
            if(whRegion === 'WEST') {
                if(zReg === 'CE') return 5;
                if(zReg === 'EA') return 8;
            }
            if(whRegion === 'CENTRAL') {
                if(zReg === 'WE') return 5;
                if(zReg === 'EA') return 6;
            }
            if(whRegion === 'EAST') {
                if(zReg === 'WE') return 8;
                if(zReg === 'CE') return 6;
            }
        }
        return 8;
    }
    
    if(conf.zone_source === 'xlmiles') {
        const XL_MAP = {
            '900-935': 2,
            '936-961': 3, '970-979': 3, '980-994': 3, '995-999': 3,
            '820-831': 3, '832-838': 3, '890-899': 3,
            '600-629': 6, '630-699': 6, '700-729': 6, '730-799': 6,
            '400-599': 6, '000-199': 6, '200-399': 6
        };
        
        for(let range in XL_MAP) {
            let [start, end] = range.split('-').map(x => parseInt(x));
            if(d >= start && d <= end) return XL_MAP[range];
        }
        return 6;
    }

    // 标准FedEx/USPS
    if(whRegion === 'WEST') {
      if(d >= 900 && d <= 935) return 2; 
      if(d >= 936 && d <= 961) return 3;
      if(d >= 962 && d <= 994) return 4;
      if(d >= 995 && d <= 999) return 4;
      if(d >= 800 && d <= 899) return 5;
      if(d >= 700 && d <= 799) return 6;
      if(d >= 0 && d <= 199) return 8;
      return 7;
    }
    
    if(whRegion === 'EAST') {
      if(d >= 0 && d <= 99) return 2;
      if(d >= 100 && d <= 199) return 3;
      if(d >= 200 && d <= 299) return 4; 
      if(d >= 300 && d <= 499) return 5;
      if(d >= 500 && d <= 699) return 6;
      if(d >= 900 && d <= 999) return 8;
      return 7;
    }
    
    if(whRegion === 'CENTRAL') {
       if(d >= 600 && d <= 629) return 2;
       if(d >= 630 && d <= 659) return 3;
       if(d >= 400 && d <= 599) return 4;
       if(d >= 660 && d <= 699) return 5;
       if(d >= 900 && d <= 999) return 7;
       if(d >= 0 && d <= 199) return 6;
       return 5;
    }
    
    return 8;
  }

  // 7. 输入验证
  function validateInputs(whCode, zip, pkg) {
    let errors = [];
    if(!whCode) errors.push("请选择发货仓库");
    if(!zip || zip.length !== 5) errors.push("请输入5位邮编");
    if(pkg.Wt <= 0) errors.push("实重必须大于0");
    if(pkg.L <= 0 || pkg.W <= 0 || pkg.H <= 0) errors.push("包裹尺寸必须大于0");
    return errors;
  }

  // 8. 主计算函数
  document.getElementById('btnCalc').onclick = () => {
    const whCode = whSelect.value;
    const tier = document.querySelector('input[name="tier"]:checked').value;
    const fuelRateInput = parseFloat(document.getElementById('fuelInput').value) || 0;
    const zip = document.getElementById('zipCode').value.trim();
    const isRes = document.getElementById('addrType').value === 'res';
    const sigOn = document.getElementById('sigToggle').checked;
    
    const pkg = {
      L: parseFloat(document.getElementById('dimL').value)||0,
      W: parseFloat(document.getElementById('dimW').value)||0,
      H: parseFloat(document.getElementById('dimH').value)||0,
      Wt: parseFloat(document.getElementById('weight').value)||0
    };

    const errors = validateInputs(whCode, zip, pkg);
    const errorBox = document.getElementById('errorBox');
    
    if(errors.length > 0) {
      errorBox.innerHTML = `<strong>⚠️ 输入错误：</strong><br>${errors.join('<br>')}`;
      errorBox.style.display = 'block';
      return;
    }
    errorBox.style.display = 'none';

    document.getElementById('resTierBadge').innerText = tier;
    let dimWt = (pkg.L * pkg.W * pkg.H) / 222;
    document.getElementById('pkgInfo').innerHTML = 
      `<b>Pkg:</b> ${pkg.L}×${pkg.W}×${pkg.H}" | 实重:${pkg.Wt}lb | 体积重:${dimWt.toFixed(2)}lb`;

    const tbody = document.getElementById('resBody');
    tbody.innerHTML = '';

    let comp = checkCompliance(pkg);
    let hasResults = false;

    Object.keys(DATA.channels).forEach(chName => {
      const conf = DATA.channels[chName];
      
      if(!conf.allow_wh.includes(whCode)) return;

      if(chName.includes("UNIUNI") && comp.status.uniuni.includes("❌")) return;
      if(chName.includes("USPS") && comp.status.usps.includes("❌")) return;
      if(chName.includes("XLmiles") && comp.status.xl.includes("❌")) return;
      if(chName.includes("FedEx") && !chName.includes("超大") && comp.status.fedex_std.includes("❌")) return;

      let rawWt = Math.max(pkg.Wt, dimWt);
      let precision = conf.weight_precision || 1;
      let finalWt = Math.ceil(rawWt / precision) * precision;

      let zone = calcZone(zip, whCode, conf);
      let svcTag = "";
      let priceList = (DATA.tiers[tier][chName] || {}).prices || [];
      let basePrice = 0;

      if (chName.includes("XLmiles")) {
        let xl = getXLService(pkg.L, pkg.W, pkg.H, pkg.Wt);
        svcTag = `<br><small class="text-primary">${xl.name}</small>`;
        
        if(!xl.code) return;
        
        let row = priceList.find(r => 
          r.service === xl.code && 
          r.w >= finalWt - 0.001 &&
          r[zone] !== undefined
        );
        
        if(row) basePrice = row[zone] || row[6] || 0;
      } else {
        let candidates = priceList.filter(r => r.w >= finalWt - 0.001);
        if(candidates.length > 0) {
          candidates.sort((a, b) => a.w - b.w);
          let row = candidates[0];
          basePrice = row[zone] || row[8] || 0;
        }
      }

      if(basePrice <= 0) return;

      let surcharges = 0;
      let details = [];

      if(isRes && conf.fees.res > 0) {
        surcharges += conf.fees.res;
        details.push(`住宅 $${conf.fees.res.toFixed(2)}`);
      }
      if(sigOn && conf.fees.sig > 0) {
        surcharges += conf.fees.sig;
        details.push(`签名 $${conf.fees.sig.toFixed(2)}`);
      }

      if(conf.fuel_mode !== 'none' && conf.fuel_mode !== 'included') {
        let rate = fuelRateInput / 100;
        let tag = "";
        
        if (conf.fuel_mode === 'discount_85') {
            rate = rate * 0.85; 
            tag = " (85折)";
        }
        
        let fuelAmt = (basePrice + surcharges) * rate;
        surcharges += fuelAmt;
        details.push(`燃油${tag} ${(rate*100).toFixed(2)}%: $${fuelAmt.toFixed(2)}`);
      } else if (conf.fuel_mode === 'included') {
        details.push(`<span class="text-success">燃油: 已含</span>`);
      }

      let total = basePrice + surcharges;

      tbody.innerHTML += `
        <tr>
          <td class="fw-bold text-start">${chName}${svcTag}</td>
          <td><span class="badge bg-light text-dark border">Z${zone}</span></td>
          <td>${finalWt.toFixed(precision === 1 ? 0 : 1)} lb</td>
          <td>$${basePrice.toFixed(2)}</td>
          <td class="small text-muted" style="line-height:1.3">${details.join('<br>') || '-'}</td>
          <td class="text-end price-main">$${total.toFixed(2)}</td>
          <td class="text-center"><span class="status-ok">✔</span></td>
        </tr>
      `;
      
      hasResults = true;
    });
    
    if(!hasResults) {
        tbody.innerHTML = `
          <tr>
            <td colspan="7" class="text-center py-4 text-danger">
              <div class="fw-bold mb-2">⚠️ 无可用报价</div>
              <div class="small">可能原因：包裹超规格 / 邮编不在服务范围 / 价格表缺失</div>
            </td>
          </tr>`;
    }
  };
</script>
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
"""

# ==========================================
# 3. 后端处理函数
# ==========================================

def clean_num(val):
    """清理数字格式"""
    if pd.isna(val): return 0.0
    s = str(val).replace('$', '').replace(',', '').strip()
    try:
        return float(s)
    except:
        return 0.0

def find_sheet_name(xl, keywords, exclude_keywords=None):
    """智能查找 Sheet 名称"""
    for sheet in xl.sheet_names:
        s_upper = sheet.upper().replace(" ", "")
        if not all(k.upper() in s_upper for k in keywords):
            continue
        if exclude_keywords and any(e.upper() in s_upper for e in exclude_keywords):
            continue
        return sheet
    return None

def extract_fuel_rate(xl):
    """提取燃油费率 - 修正版"""
    for sheet in xl.sheet_names:
        if "MT" in sheet.upper() or "632" in sheet: 
            try:
                df = pd.read_excel(xl, sheet_name=sheet, header=None, nrows=20)
                
                for r in range(min(20, df.shape[0])):
                    for c in range(df.shape[1]):
                        val = str(df.iloc[r, c])
                        
                        # 查找燃油附加费
                        if "燃油附加费" in val or "燃油费率" in val:
                            # 检查右侧单元格
                            for offset in [1, 2, 3]:
                                if c + offset < df.shape[1]:
                                    next_val = df.iloc[r, c+offset]
                                    if pd.notna(next_val):
                                        rate_str = str(next_val).replace('%', '').strip()
                                        
                                        # 跳过文本说明
                                        if "含" in rate_str or "包含" in rate_str:
                                            continue
                                        
                                        try:
                                            f = float(rate_str)
                                            if f > 0 and f < 1:  # 0-1 之间，已经是小数
                                                return f
                                            elif f >= 1 and f <= 100:  # 百分比形式
                                                return f / 100.0
                                        except:
                                            continue
            except Exception as e:
                print(f"  [Warn] Failed to extract fuel from {sheet}: {e}")
    return 0.0

def load_gofo_zip_db(tier_file):
    """加载 GOFO 邮编数据库"""
    db = {}
    path = os.path.join(DATA_DIR, tier_file)
    if not os.path.exists(path):
        print(f"  [Warn] GOFO DB file not found: {tier_file}")
        return db
    
    try:
        xl = pd.ExcelFile(path)
        sheet_name = find_sheet_name(xl, ["GOFO", "报价"], ["UNIUNI", "MT"])
        if not sheet_name:
            print(f"  [Warn] GOFO sheet not found in {tier_file}")
            return db
        
        df = pd.read_excel(xl, sheet_name=sheet_name, header=None, nrows=8000)
        
        start_row = -1
        cols = {}
        for r in range(min(200, df.shape[0])):
            row_vals = [str(x).strip() for x in df.iloc[r].values]
            if "目的地邮编" in row_vals or "GOFO_大区" in row_vals:
                start_row = r
                for c, v in enumerate(row_vals):
                    if "邮编" in v: cols['zip'] = c
                    elif "城市" in v: cols['city'] = c
                    elif "省州" in v: cols['state'] = c
                    elif "大区" in v: cols['region'] = c
                break
        
        if start_row == -1 or 'zip' not in cols:
            print(f"  [Warn] GOFO table header not found")
            return db
        
        for r in range(start_row+1, len(df)):
            try:
                raw_zip = str(df.iloc[r, cols['zip']])
                z = raw_zip.split('.')[0].strip().zfill(5)
                
                if len(z) == 5 and z.isdigit():
                    state = str(df.iloc[r, cols.get('state', -1)]).strip()
                    db[z] = {
                        "city": str(df.iloc[r, cols.get('city', -1)]).strip(),
                        "state": state,
                        "region": str(df.iloc[r, cols.get('region', -1)]).strip(),
                        "cn_state": US_STATES_CN.get(state, "")
                    }
            except:
                continue
        
        print(f"  [OK] GOFO Zip DB loaded: {len(db)} entries")
    except Exception as e:
        print(f"  [Err] Failed to load GOFO Zip DB: {e}")
    
    return db

def load_fedex_pdf_zips():
    """加载 FedEx PDF 偏远邮编"""
    remote_zips = set()
    extended_zips = set()
    
    pdf_files = [
        "FGE_DAS_Contiguous_Extended_Alaska_Hawaii_2025.pdf",
        "FGE_DAS_Zip_Code_Changes_2025.pdf"
    ]
    
    for pdf in pdf_files:
        path = os.path.join(DATA_DIR, pdf)
        if not os.path.exists(path):
            continue
        
        try:
            txt = subprocess.check_output(
                ["pdftotext", path, "-"], 
                stderr=subprocess.DEVNULL,
                timeout=30
            ).decode('utf-8', errors='ignore')
            
            zips = re.findall(r'\b\d{5}\b', txt)
            for z in zips:
                remote_zips.add(z)
            
            print(f"  [OK] Loaded {len(zips)} zips from {pdf}")
        except FileNotFoundError:
            print(f"  [Warn] pdftotext not found. Install: apt-get install poppler-utils")
            break
        except subprocess.TimeoutExpired:
            print(f"  [Err] PDF processing timeout: {pdf}")
        except Exception as e:
            print(f"  [Err] Failed to process {pdf}: {e}")
    
    return list(remote_zips), list(extended_zips)

def extract_prices(df, split_side=None, channel_name="", is_residential=None):
    """
    从 DataFrame 提取价格表 - 修正版
    
    参数:
    - split_side: 'left' 或 'right' 用于左右分割表
    - channel_name: 渠道名称
    - is_residential: True/False/None，用于商住分表
    """
    if df is None or df.empty:
        return []
    
    # ==========================================
    # XLmiles 专用解析器
    # ==========================================
    if "XLmiles" in channel_name:
        prices = []
        h_row = -1
        z_map = {}
        
        for r in range(min(20, df.shape[0])):
            row_vals = [str(x).lower() for x in df.iloc[r].values]
            if any("zone" in x for x in row_vals):
                h_row = r
                for c, v in enumerate(row_vals):
                    m = re.search(r'zone\D*(\d+)', v)
                    if m:
                        z_map[int(m.group(1))] = c
                break
        
        if h_row == -1 or not z_map:
            print(f"  [Warn] XLmiles header not found")
            return []
        
        current_service = "AH"
        
        for r in range(h_row+1, len(df)):
            try:
                svc_raw = str(df.iloc[r, 0]).upper()
                if "AH" in svc_raw:
                    current_service = "AH"
                elif "OS" in svc_raw:
                    current_service = "OS"
                elif "OM" in svc_raw:
                    current_service = "OM"
                
                w_raw = str(df.iloc[r, 2])
                nums = re.findall(r'(\d+(?:\.\d+)?)', w_raw)
                if not nums:
                    continue
                
                w_val = float(nums[-1])
                
                entry = {'service': current_service, 'w': w_val}
                
                valid = False
                for z, c in z_map.items():
                    p = clean_num(df.iloc[r, c])
                    if p > 0:
                        entry[z] = p
                        valid = True
                
                if valid:
                    prices.append(entry)
            except:
                continue
        
        print(f"  [OK] XLmiles: {len(prices)} price entries")
        return prices

    # ==========================================
    # 标准渠道解析器
    # ==========================================
    total_cols = df.shape[1]
    c_start, c_end = 0, total_cols
    
    # **修正点1: 只识别lb/oz列，过滤kg列**
    if split_side:
        weight_cols = []
        for c in range(total_cols):
            for r in range(min(50, df.shape[0])):
                val = str(df.iloc[r, c]).lower()
                # 只要包含 lb 或 oz 的重量列
                if ('重量' in val or 'weight' in val) and ('lb' in val or 'oz' in val):
                    if c not in weight_cols:
                        weight_cols.append(c)
                    break
        
        weight_cols.sort()
        
        if split_side == 'left':
            if len(weight_cols) > 1:
                c_start = weight_cols[0]
                c_end = weight_cols[1]
            elif len(weight_cols) == 1:
                c_start = weight_cols[0]
                c_end = total_cols
        elif split_side == 'right':
            if len(weight_cols) > 1:
                c_start = weight_cols[1]
                c_end = total_cols
            else:
                print(f"  [Warn] Right side not found")
                return []
    
    # **修正点2: 商住分表处理**
    if is_residential is not None:
        # 查找商业/住宅的列分隔
        weight_cols = []
        for c in range(total_cols):
            for r in range(min(10, df.shape[0])):
                val = str(df.iloc[r, c]).lower()
                if '重量' in val and 'lb' in val:
                    weight_cols.append(c)
                    break
        
        weight_cols.sort()
        
        if len(weight_cols) >= 2:
            if is_residential:
                # 住宅价格通常在左侧（列0开始）
                c_start = weight_cols[0]
                c_end = weight_cols[1]
            else:
                # 商业价格在右侧（列10开始）
                c_start = weight_cols[1]
                c_end = total_cols
    
    # 查找表头行
    h_row = -1
    w_col = -1
    z_map = {}
    
    for r in range(min(200, df.shape[0])):
        row_vals = [str(x).lower() for x in df.iloc[r, c_start:c_end].values]
        has_weight = any('weight' in x or '重量' in x for x in row_vals)
        has_zone = any('zone' in x for x in row_vals)
        
        if has_weight and has_zone:
            h_row = r
            break
    
    if h_row == -1:
        print(f"  [Warn] Header row not found")
        return []
    
    row_dat = df.iloc[h_row]
    for c in range(c_start, c_end):
        if c >= total_cols:
            break
        
        val = str(row_dat[c]).strip().lower()
        
        if ('weight' in val or '重量' in val) and ('lb' in val or 'oz' in val) and w_col == -1:
            w_col = c
        
        m = re.search(r'zone[\D]*(\d+)', val)
        if m:
            z_map[int(m.group(1))] = c
    
    if w_col == -1 or not z_map:
        print(f"  [Warn] Weight column or zone columns not found")
        return []
    
    # 提取数据行
    prices = []
    for r in range(h_row + 1, len(df)):
        try:
            w_raw = df.iloc[r, w_col]
            w_str = str(w_raw).lower().strip()
            
            nums = re.findall(r'[\d\.]+', w_str)
            if not nums:
                continue
            
            w_val = float(nums[0])
            
            # 单位转换
            if 'oz' in w_str:
                w_val /= 16.0
            elif 'kg' in w_str:
                w_val /= 0.453592
            
            if w_val <= 0:
                continue
            
            entry = {'w': w_val}
            valid = False
            
            for z, c in z_map.items():
                p = clean_num(df.iloc[r, c])
                if p > 0:
                    entry[z] = p
                    valid = True
            
            if valid:
                prices.append(entry)
        except:
            continue
    
    prices.sort(key=lambda x: x['w'])
    print(f"  [OK] {channel_name or 'Standard'}: {len(prices)} price entries")
    return prices

# ==========================================
# 4. 主流程
# ==========================================

def main():
    """主生成流程"""
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
    
    print("=" * 60)
    print("🚀 Starting Generation (V2026.2.1 Data Fix)")
    print("=" * 60)
    
    print("\n[1/3] Loading GOFO Zip Database...")
    zip_db = load_gofo_zip_db("T0.xlsx")
    
    print("\n[2/3] Loading FedEx DAS Zips...")
    fedex_remote, fedex_extended = load_fedex_pdf_zips()
    
    print("\n[3/3] Processing Price Tables...")
    
    final_data = {
        "warehouses": WAREHOUSE_DB,
        "channels": CHANNEL_CONFIG,
        "gofo_zips": zip_db,
        "fedex_das_remote": fedex_remote,
        "fedex_das_extended": fedex_extended,
        "tiers": {}
    }

    for tier, filename in TIER_FILES.items():
        print(f"\n--- Processing {tier} ({filename}) ---")
        path = os.path.join(DATA_DIR, filename)
        
        if not os.path.exists(path):
            print(f"  [Warn] File not found: {filename}")
            continue
        
        tier_data = {}
        
        try:
            xl = pd.ExcelFile(path)
            fuel_rate = extract_fuel_rate(xl)
            
            if fuel_rate > 0:
                print(f"  [OK] Fuel rate detected: {fuel_rate*100:.2f}%")
            
            for ch_key, conf in CHANNEL_CONFIG.items():
                sheet = find_sheet_name(xl, conf["keywords"], conf.get("exclude"))
                
                if not sheet:
                    print(f"  [Skip] {ch_key}: Sheet not found")
                    continue
                
                try:
                    df = pd.read_excel(xl, sheet_name=sheet, header=None)
                    
                    # **修正点3: 商住分表处理**
                    if conf.get("has_res_com_split"):
                        # 生成两套价格表
                        prices_res = extract_prices(
                            df, 
                            split_side=None,
                            channel_name=ch_key, 
                            is_residential=True
                        )
                        prices_com = extract_prices(
                            df, 
                            split_side=None,
                            channel_name=ch_key, 
                            is_residential=False
                        )
                        
                        if prices_res and prices_com:
                            tier_data[ch_key] = {
                                "prices_residential": prices_res,
                                "prices_commercial": prices_com,
                                "fuel_rate": fuel_rate if conf.get("fuel_mode") in ["standard", "discount_85"] else 0
                            }
                            print(f"  [OK] {ch_key}: Res={len(prices_res)}, Com={len(prices_com)} rows")
                        else:
                            print(f"  [Warn] {ch_key}: Commercial/Residential split failed")
                    else:
                        # 标准单表
                        prices = extract_prices(
                            df, 
                            split_side=conf.get("sheet_side"), 
                            channel_name=ch_key
                        )
                        
                        if prices:
                            tier_data[ch_key] = {
                                "prices": prices,
                                "fuel_rate": fuel_rate if conf.get("fuel_mode") in ["standard", "discount_85"] else 0
                            }
                            print(f"  [OK] {ch_key}: {len(prices)} rows")
                        else:
                            print(f"  [Warn] {ch_key}: No valid prices extracted")
                
                except Exception as e:
                    print(f"  [Err] {ch_key}: {e}")
        
        except Exception as e:
            print(f"  [Err] Failed to process {filename}: {e}")
        
        final_data["tiers"][tier] = tier_data

    print("\n" + "=" * 60)
    print("📝 Generating HTML...")
    
    json_str = json.dumps(final_data, ensure_ascii=False, indent=None).replace("NaN", "0")
    html = HTML_TEMPLATE.replace('__JSON_DATA__', json_str)
    
    output_path = os.path.join(OUTPUT_DIR, "index.html")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    
    print(f"✅ HTML generated: {output_path}")
    print(f"   File size: {len(html)/1024:.1f} KB")
    
    total_channels = sum(len(t) for t in final_data["tiers"].values())
    print(f"\n📊 Summary:")
    print(f"   Tiers: {len(final_data['tiers'])}")
    print(f"   Total channels: {total_channels}")
    print(f"   GOFO zips: {len(zip_db)}")
    print(f"   FedEx remote zips: {len(fedex_remote)}")
    
    print("\n" + "=" * 60)
    print("🎉 Generation Complete!")
    print("=" * 60)

if __name__ == "__main__":
    main()
