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
        return
    try:
        with open(DB_FILE, 'r', encoding='utf-8') as f:
            GLOBAL_DATA_LIST = json.load(f)
        GLOBAL_TAG_MAP = { item['t'].replace('_', ' ').lower(): item for item in GLOBAL_DATA_LIST }
        print(f"✅ 基础数据库加载完毕！包含 {len(GLOBAL_DATA_LIST)} 条数据。")
    except Exception as e:
        print(f"❌ 数据库加载失败: {e}")

init_db()

@app.route('/')
def index(): 
    return render_template('index.html')

# --- API: 获取配置 (只读) ---
@app.route('/api/load_config', methods=['GET'])
def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f: 
            data = json.load(f)
        return jsonify({"status": "success", "mapping": data.get("mapping", []), "order": data.get("order", [])})
    return jsonify({"status": "success", "mapping": [], "order": []})

# --- API: 获取目录结构 (只读) ---
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

# --- API: 获取具体标签 (只读) ---
@app.route('/api/get_category_tags', methods=['POST'])
def get_category_tags():
    data = request.json
    target_cat = data.get('cat')
    target_sub = data.get('sub')
    
    filtered_tags = []
    limit = 3000 
    
    for item in GLOBAL_DATA_LIST:
        item_cat = item['c'] if item['c'] else "未分类"
        item_sub = item['s'] if item['s'] else "基础"
        if item_cat == target_cat and item_sub == target_sub:
            filtered_tags.append({ "tag": item['t'], "trans": item['zh'] })
            if len(filtered_tags) >= limit: break
                
    return jsonify({ "tags": filtered_tags })

# --- API: 翻译 ---
@app.route('/api/translate_tag', methods=['POST'])
def translate_tag():
    if not HAS_TRANSLATOR: return jsonify({"trans": "无翻译库"})
    text = request.json.get('text', '')
    try:
        res = GoogleTranslator(source='auto', target='zh-CN').translate(text)
        return jsonify({"trans": res})
    except: return jsonify({"trans": "Error"})

# --- API: 搜索 ---
@app.route('/api/search_tags', methods=['POST'])
def search_tags():
    data = request.json
    query = data.get('query', '').lower().strip()
    results = []
    count = 0
    for item in GLOBAL_DATA_LIST:
        if query in item['t'] or (item['zh'] and query in item['zh']):
            results.append({ "tag": item['t'], "trans": item['zh'], "cat": item['c'], "sub": item['s'] })
            count += 1
            if count >= 50: break
    return jsonify({"results": results})

# --- API: Process (只用服务器数据处理) ---
# 注意：前端会把用户的私有数据再次合并，这里只负责基础处理
@app.route('/api/process', methods=['POST'])
def process():
    data = request.json
    input_tags = [t.strip() for t in data.get('tags', '').split(',') if t.strip()]
    deduplicate = data.get('deduplicate', False)
    mapping_list = data.get('mapping', [])
    target_order = data.get('order', [])
    default_cat = data.get('default_category', '未归类词')

    mapping_rule = {}
    for item in mapping_list:
        if len(item) >= 3: mapping_rule[(item[0], item[1])] = item[2]

    if deduplicate:
        seen = set()
        unique_list = []
        for t in input_tags:
            low = t.lower()
            if low not in seen:
                seen.add(low)
                unique_list.append(t)
        input_tags = unique_list

    result_buckets = defaultdict(list)
    for cat in target_order: result_buckets[cat] = []
        
    for tag in input_tags:
        clean_key = tag.lower().replace('_', ' ')
        info = GLOBAL_TAG_MAP.get(clean_key)
        
        if info:
            origin_cat = info['c']
            origin_sub = info['s']
            target_cat = mapping_rule.get((origin_cat, origin_sub))
            if not target_cat: target_cat = origin_cat
            if not target_cat: target_cat = default_cat
            
            if target_cat not in result_buckets: result_buckets[target_cat] = []
            result_buckets[target_cat].append({ "tag": tag, "trans": info['zh'] })
        else:
            if default_cat not in result_buckets: result_buckets[default_cat] = []
            result_buckets[default_cat].append({ "tag": tag, "trans": "" })

    return jsonify({ "status": "success", "result_struct": result_buckets })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)