import os
import json
from collections import defaultdict
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS

# 引入翻译库 (可选)
try:
    from deep_translator import GoogleTranslator
    HAS_TRANSLATOR = True
except ImportError:
    HAS_TRANSLATOR = False
    print("提示: 未安装 deep-translator，翻译功能不可用。")

app = Flask(__name__)
CORS(app)

# --- 配置 ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(BASE_DIR, "danbooru.json") 
CONFIG_FILE = os.path.join(BASE_DIR, "defaults_config.json")

# --- 全局内存数据库 ---
GLOBAL_DATA_LIST = []  
GLOBAL_TAG_MAP = {}    

def init_db():
    global GLOBAL_DATA_LIST, GLOBAL_TAG_MAP
    
    if not os.path.exists(DB_FILE):
        print("="*50)
        print(f"❌ 错误：找不到数据库文件 {DB_FILE}")
        print("💡 请先运行 convert_db.py 将 Excel 转换为 JSON！")
        print("="*50)
        return

    print(f"🚀 正在极速加载数据库: {DB_FILE} ...")
    try:
        with open(DB_FILE, 'r', encoding='utf-8') as f:
            GLOBAL_DATA_LIST = json.load(f)
            
        GLOBAL_TAG_MAP = {
            item['t'].replace('_', ' ').lower(): item 
            for item in GLOBAL_DATA_LIST
        }
        
        print(f"✅ 数据库加载完毕！包含 {len(GLOBAL_DATA_LIST)} 条数据。")
    except Exception as e:
        print(f"❌ 数据库加载失败: {e}")

@app.route('/')
def index(): 
    return render_template('index.html')

# --- API: 获取配置 ---
@app.route('/api/load_config', methods=['GET'])
def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f: 
            data = json.load(f)
        return jsonify({
            "status": "success", 
            "mapping": data.get("mapping", []), 
            "order": data.get("order", [])
        })
    return jsonify({"status": "error", "message": "Config file not found"})

# --- API: 核心整理功能 (已修复分类失效问题) ---
@app.route('/api/process', methods=['POST'])
def process():
    try:
        data = request.json
        input_tags = data.get('tags', '')
        deduplicate = data.get('deduplicate', False)
        
        mapping_list = data.get('mapping', [])
        target_order = data.get('order', [])
        default_cat = data.get('default_category', '未归类词')

        # 构建映射规则
        mapping_rule = {}
        for item in mapping_list:
            if len(item) >= 3: 
                mapping_rule[(item[0], item[1])] = item[2]

        raw_list = [t.strip() for t in input_tags.split(',') if t.strip()]
        
        if deduplicate:
            seen = set()
            unique_list = []
            for t in raw_list:
                low = t.lower()
                if low not in seen:
                    seen.add(low)
                    unique_list.append(t)
            raw_list = unique_list

        result_buckets = defaultdict(list)
        
        # 预填充顺序 (如果有配置)
        for cat in target_order:
            result_buckets[cat] = []
            
        for tag in raw_list:
            clean_key = tag.lower().replace('_', ' ')
            info = GLOBAL_TAG_MAP.get(clean_key)
            
            if info:
                origin_cat = info['c'] # 数据库里的原分类
                origin_sub = info['s']
                trans = info['zh']
                
                # 1. 尝试使用映射规则
                target_cat = mapping_rule.get((origin_cat, origin_sub))
                
                # 2. 如果没有映射规则，直接使用数据库里的原分类 (修复核心)
                if not target_cat:
                    target_cat = origin_cat
                
                # 3. 如果还是空的，才用默认分类
                if not target_cat:
                    target_cat = default_cat
                
                # 放入对应的桶
                if target_cat not in result_buckets:
                    # 如果这个分类不在预设顺序里，追加到最后
                    result_buckets[target_cat] = []
                    
                result_buckets[target_cat].append({ "tag": tag, "trans": trans })
            else:
                # 未命中的词
                if default_cat not in result_buckets:
                    result_buckets[default_cat] = []
                result_buckets[default_cat].append({ "tag": tag, "trans": "" })

        return jsonify({ "status": "success", "result_struct": result_buckets })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# --- API: 获取目录结构 ---
@app.route('/api/get_dictionary_structure', methods=['GET'])
def get_dictionary_structure():
    if not GLOBAL_DATA_LIST:
        return jsonify({"structure": {}, "status": "empty"})
    
    structure = defaultdict(set)
    for item in GLOBAL_DATA_LIST:
        cat = item['c'] if item['c'] else "未分类"
        sub = item['s'] if item['s'] else "基础"
        structure[cat].add(sub)
    
    final_structure = {cat: sorted(list(subs)) for cat, subs in structure.items()}
    return jsonify({ "structure": final_structure, "status": "success" })

# --- API: 获取具体标签 ---
@app.route('/api/get_category_tags', methods=['POST'])
def get_category_tags():
    data = request.json
    target_cat = data.get('cat')
    target_sub = data.get('sub')
    
    if not GLOBAL_DATA_LIST:
        return jsonify({"tags": []})
        
    filtered_tags = []
    limit = 2000 
    
    for item in GLOBAL_DATA_LIST:
        item_cat = item['c'] if item['c'] else "未分类"
        item_sub = item['s'] if item['s'] else "基础"
        
        if item_cat == target_cat and item_sub == target_sub:
            filtered_tags.append({ "tag": item['t'], "trans": item['zh'] })
            if len(filtered_tags) >= limit:
                break
                
    return jsonify({ "tags": filtered_tags, "truncated": len(filtered_tags) >= limit })

# --- API: 搜索 ---
@app.route('/api/search_tags', methods=['POST'])
def search_tags():
    data = request.json
    query = data.get('query', '').lower().strip()
    
    if not query or not GLOBAL_DATA_LIST:
        return jsonify({"results": []})
    
    results = []
    count = 0
    limit = 50 
    
    for item in GLOBAL_DATA_LIST:
        if query in item['t'] or (item['zh'] and query in item['zh']):
            results.append({
                "tag": item['t'],
                "trans": item['zh']
            })
            count += 1
            if count >= limit:
                break
                
    return jsonify({"results": results})

# --- API: 翻译 ---
@app.route('/api/translate_tag', methods=['POST'])
def translate_tag():
    if not HAS_TRANSLATOR:
        return jsonify({"trans": "无翻译库", "status": "warning"})
    text = request.json.get('text', '')
    if not text: return jsonify({"trans": ""})
    try:
        res = GoogleTranslator(source='auto', target='zh-CN').translate(text)
        return jsonify({"trans": res})
    except:
        return jsonify({"trans": "Error"})

# --- API: 保存/修改标签 ---
@app.route('/api/save_tag', methods=['POST'])
def save_tag():
    try:
        data = request.json
        tag = data.get('tag', '').strip().lower()
        trans = data.get('trans', '').strip()
        cat = data.get('cat', '').strip()
        sub = data.get('sub', '').strip()

        if not tag or not cat or not sub:
            return jsonify({"status": "error", "message": "信息不完整"})

        clean_key = tag.replace('_', ' ')
        new_item = { "t": tag, "zh": trans, "c": cat, "s": sub }
        GLOBAL_TAG_MAP[clean_key] = new_item

        found = False
        for i, item in enumerate(GLOBAL_DATA_LIST):
            if item['t'] == tag:
                GLOBAL_DATA_LIST[i] = new_item
                found = True
                break
        if not found:
            GLOBAL_DATA_LIST.append(new_item)

        with open(DB_FILE, 'w', encoding='utf-8') as f:
            json.dump(GLOBAL_DATA_LIST, f, ensure_ascii=False, separators=(',', ':'))

        return jsonify({"status": "success", "message": "保存成功！"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# --- API: 删除条目 ---
@app.route('/api/delete_item', methods=['POST'])
def delete_item():
    try:
        data = request.json
        delete_type = data.get('type') 
        target = data.get('target')
        parent = data.get('parent')

        if not target: return jsonify({"status": "error", "message": "目标为空"})

        global GLOBAL_DATA_LIST
        deleted_count = 0
        new_list = []

        for item in GLOBAL_DATA_LIST:
            should_delete = False
            if delete_type == 'tag':
                if item['t'] == target: should_delete = True
            elif delete_type == 'minor':
                if item['s'] == target and item['c'] == parent: should_delete = True
            elif delete_type == 'major':
                if item['c'] == target: should_delete = True

            if should_delete:
                clean_key = item['t'].replace('_', ' ').lower()
                if clean_key in GLOBAL_TAG_MAP:
                    del GLOBAL_TAG_MAP[clean_key]
                deleted_count += 1
            else:
                new_list.append(item)

        GLOBAL_DATA_LIST = new_list

        with open(DB_FILE, 'w', encoding='utf-8') as f:
            json.dump(GLOBAL_DATA_LIST, f, ensure_ascii=False, separators=(',', ':'))

        return jsonify({"status": "success", "message": f"已删除 {deleted_count} 个条目"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# --- API: 保存排序 ---
@app.route('/api/save_category_order', methods=['POST'])
def save_category_order():
    try:
        data = request.json
        new_order = data.get('order', [])
        
        if not new_order: return jsonify({"status": "error"})

        config = {}
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
        
        config['order'] = new_order
        
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=4)
            
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# ... (前面的代码不变) ...

# 1. 在这里直接调用初始化，确保 Gunicorn 启动时也会加载数据
init_db()

if __name__ == '__main__':
    print("=" * 50)
    print("赛博猫猫 Tag Sorter (终极版) 启动成功喵!")
    print("请双击 '启动程序.bat' 来使用工具喵！")
    print("=" * 50)
    app.run(host='0.0.0.0', port=5000, debug=False)