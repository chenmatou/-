/**
 * 前端JS补丁 - 修复商业/住宅分表逻辑
 * 
 * 将此代码替换 generate_fixed.py 中 HTML_TEMPLATE 内的主计算函数
 */

// 8. 主计算函数（完整修复版）
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
      `<b>Pkg:</b> ${pkg.L}×${pkg.W}×${pkg.H}" | 实重:${pkg.Wt}lb | 体积重:${dimWt.toFixed(2)}lb | 地址:${isRes ? '住宅' : '商业'}`;

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
      
      // ============================================
      // 【修复点1】商业/住宅分表处理
      // ============================================
      const channelData = DATA.tiers[tier][chName] || {};
      let priceList = [];
      
      // 检查是否有商住分表
      if (channelData.prices_residential && channelData.prices_commercial) {
          priceList = isRes ? channelData.prices_residential : channelData.prices_commercial;
          svcTag += isRes ? '<br><small class="text-info">住宅价格</small>' : '<br><small class="text-success">商业价格</small>';
      } else {
          priceList = channelData.prices || [];
      }
      
      if (!priceList || priceList.length === 0) {
          console.log(`${chName}: No price list available`);
          return;
      }
      
      let basePrice = 0;

      // ============================================
      // 【修复点2】XLmiles 专用查找
      // ============================================
      if (chName.includes("XLmiles")) {
        let xl = getXLService(pkg.L, pkg.W, pkg.H, pkg.Wt);
        svcTag += `<br><small class="text-primary">${xl.name}</small>`;
        
        if(!xl.code) return;
        
        // 按服务类型和重量查找
        let row = priceList.find(r => 
          r.service === xl.code && 
          r.w >= finalWt - 0.001 &&
          r[zone] !== undefined
        );
        
        if(row) {
            basePrice = row[zone] || row[6] || 0;
        }
      } else {
        // ============================================
        // 【修复点3】标准查找（向上取整匹配）
        // ============================================
        let candidates = priceList.filter(r => r.w >= finalWt - 0.001);
        
        if(candidates.length > 0) {
          // 找到最接近的重量档位
          candidates.sort((a, b) => a.w - b.w);
          let row = candidates[0];
          
          // 尝试找到对应Zone的价格
          if (row[zone] !== undefined) {
              basePrice = row[zone];
          } else if (row[8] !== undefined) {
              // Fallback to Zone 8
              basePrice = row[8];
          } else {
              // 取第一个有效Zone的价格
              for (let z = 2; z <= 9; z++) {
                  if (row[z] !== undefined && row[z] > 0) {
                      basePrice = row[z];
                      break;
                  }
              }
          }
        }
      }

      if(basePrice <= 0) {
          console.log(`${chName}: No valid price found for weight=${finalWt}, zone=${zone}`);
          return;
      }

      // ============================================
      // 【修复点4】附加费计算
      // ============================================
      let surcharges = 0;
      let details = [];

      // 住宅费（只在住宅地址时收取）
      if(isRes && conf.fees.res > 0) {
        surcharges += conf.fees.res;
        details.push(`住宅 $${conf.fees.res.toFixed(2)}`);
      }
      
      // 签名费
      if(sigOn && conf.fees.sig > 0) {
        surcharges += conf.fees.sig;
        details.push(`签名 $${conf.fees.sig.toFixed(2)}`);
      }

      // ============================================
      // 【修复点5】燃油费计算
      // ============================================
      if(conf.fuel_mode !== 'none' && conf.fuel_mode !== 'included') {
        let rate = fuelRateInput / 100;
        let tag = "";
        
        // 85折折扣
        if (conf.fuel_mode === 'discount_85') {
            rate = rate * 0.85; 
            tag = " (85折)";
        }
        
        let fuelAmt = (basePrice + surcharges) * rate;
        surcharges += fuelAmt;
        details.push(`燃油${tag} ${(rate*100).toFixed(2)}%: $${fuelAmt.toFixed(2)}`);
      } else if (conf.fuel_mode === 'included') {
        details.push(`<span class="text-success fw-bold">燃油: 已含</span>`);
      }

      let total = basePrice + surcharges;

      // ============================================
      // 输出结果行
      // ============================================
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
              <div class="small">可能原因：</div>
              <ul class="text-start small mb-0" style="max-width:400px; margin:0 auto;">
                <li>包裹超出渠道规格限制</li>
                <li>邮编不在服务范围内</li>
                <li>价格表数据缺失（请检查Excel）</li>
                <li>当前仓库不支持该渠道</li>
              </ul>
            </td>
          </tr>`;
    }
};
