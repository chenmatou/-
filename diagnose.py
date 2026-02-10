#!/usr/bin/env python3
"""
快速诊断工具 - 检查数据文件和环境配置
"""
import os
import sys
import subprocess

def check_python_packages():
    """检查 Python 依赖"""
    print("\n=== 检查 Python 包 ===")
    required = ['pandas', 'openpyxl']
    
    for pkg in required:
        try:
            __import__(pkg)
            print(f"✅ {pkg}: 已安装")
        except ImportError:
            print(f"❌ {pkg}: 未安装 - 请运行 pip install {pkg}")

def check_data_files():
    """检查数据文件"""
    print("\n=== 检查数据文件 ===")
    data_dir = "data"
    
    if not os.path.exists(data_dir):
        print(f"❌ {data_dir} 目录不存在")
        return
    
    required_files = ["T0.xlsx", "T1.xlsx", "T2.xlsx", "T3.xlsx"]
    
    for file in required_files:
        path = os.path.join(data_dir, file)
        if os.path.exists(path):
            size = os.path.getsize(path) / 1024
            print(f"✅ {file}: {size:.1f} KB")
        else:
            print(f"❌ {file}: 未找到")

def check_pdftotext():
    """检查 pdftotext 工具"""
    print("\n=== 检查 PDF 工具 ===")
    try:
        result = subprocess.run(
            ["pdftotext", "-v"], 
            capture_output=True, 
            timeout=5
        )
        print("✅ pdftotext: 已安装")
    except FileNotFoundError:
        print("❌ pdftotext: 未安装")
        print("   安装方法: sudo apt-get install poppler-utils")
    except Exception as e:
        print(f"⚠️  pdftotext: 检查失败 - {e}")

def check_output_dir():
    """检查输出目录"""
    print("\n=== 检查输出目录 ===")
    output_dir = "public"
    
    if os.path.exists(output_dir):
        files = os.listdir(output_dir)
        print(f"✅ {output_dir}/ 存在，包含 {len(files)} 个文件")
        
        if "index.html" in files:
            path = os.path.join(output_dir, "index.html")
            size = os.path.getsize(path) / 1024
            print(f"   - index.html: {size:.1f} KB")
    else:
        print(f"⚠️  {output_dir}/ 不存在（首次运行时会自动创建）")

def main():
    print("=" * 60)
    print("🔍 SureGo 运费计算器环境诊断工具")
    print("=" * 60)
    
    check_python_packages()
    check_data_files()
    check_pdftotext()
    check_output_dir()
    
    print("\n" + "=" * 60)
    print("💡 提示:")
    print("   1. 如果缺少依赖: pip install -r requirements.txt")
    print("   2. 如果缺少数据文件: 请将 Excel 文件放入 data/ 目录")
    print("   3. 运行生成: python generate.py")
    print("=" * 60)

if __name__ == "__main__":
    main()
