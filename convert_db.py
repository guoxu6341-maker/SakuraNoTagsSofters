import pandas as pd
import json
import os

# 配置你的 Excel 路径
INPUT_FILE = "danbooru_tags.xlsx"
OUTPUT_FILE = "danbooru.json"

def convert_excel_to_json():
    print(f"📂 正在读取 Excel: {INPUT_FILE} (这可能需要一点时间)...")
    
    try:
        # 读取 Excel，强制将所有内容视为字符串，防止数字被转成 float
        df = pd.read_excel(INPUT_FILE, dtype=str).fillna("")
        
        data_list = []
        
        print("⚡ 正在转换数据结构...")
        for _, row in df.iterrows():
            # 提取并清洗数据
            tag = row.get('english', '').strip().lower()
            cat = row.get('category', '未归类').strip()
            sub = row.get('subcategory', '基础').strip()
            
            # 处理翻译：优先取 translation 列，没有则取 chinese 列
            trans = row.get('translation', '').strip()
            if not trans:
                trans = row.get('chinese', '').strip()
                
            if tag:
                data_list.append({
                    "t": tag,      # t 代表 tag (缩短键名减小文件体积)
                    "c": cat,      # c 代表 category
                    "s": sub,      # s 代表 subcategory
                    "zh": trans    # zh 代表 中文翻译
                })
        
        print(f"💾 正在保存为 JSON: {OUTPUT_FILE} ...")
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            json.dump(data_list, f, ensure_ascii=False, separators=(',', ':')) # 使用紧凑格式保存
            
        print(f"✅ 成功！已转换 {len(data_list)} 条数据。")
        print(f"🚀 请修改 app.py 以使用新生成的 {OUTPUT_FILE}")
        
    except Exception as e:
        print(f"❌ 错误: {e}")

if __name__ == "__main__":
    convert_excel_to_json()