from flask import Flask, render_template, request, redirect, session, send_file, url_for
import json, os, pandas as pd, random, time

app = Flask(__name__)
app.secret_key = "doc_review_platform"

DOC_FOLDER = "documents"
CONFIG_FILE = "config.json"

# -------------------------
# 工具函数
# -------------------------
def load_json(file):
    if not os.path.exists(file):
        return {}
    with open(file, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except:
            return {}

def save_json(file, data):
    with open(file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def get_documents():
    docs = []
    for f in os.listdir(DOC_FOLDER):
        if f.endswith(".pdf") or f.endswith(".docx"):
            docs.append({"id": f, "name": f})
    return docs

# -------------------------
# 登录
# -------------------------
@app.route("/", methods=["GET", "POST"])
def login():
    if request.method=="POST":
        username = request.form["username"]
        password = request.form["password"]
        users = load_json("users.json")
        if username in users and users[username] == password:
            session["user"] = username
            session.pop("random_docs", None)
            return redirect("/dashboard")
        return "用户名或密码错误"
    return render_template("login.html")

# -------------------------
# 注册
# -------------------------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method=="POST":
        username = request.form["username"]
        password = request.form["password"]
        users = load_json("users.json")
        if username in users:
            return "用户已存在"
        users[username] = password
        save_json("users.json", users)
        return redirect("/")
    return render_template("register.html")

# -------------------------
# 文档列表
# -------------------------
@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect("/")

    docs = get_documents()

    if session["user"] != "admin":
        # 普通用户随机选择5个文档
        if "random_docs" not in session:
            session["random_docs"] = random.sample(docs, min(5, len(docs)))
        docs = session["random_docs"]

    return render_template("dashboard.html", docs=docs, user=session["user"])

# -------------------------
# 文档嵌入显示
# -------------------------
@app.route("/documents/<filename>")
def serve_document(filename):
    if "user" not in session:
        return redirect("/")
    path = os.path.join(DOC_FOLDER, filename)
    if not os.path.exists(path):
        return "文件不存在"
    return send_file(path)

# -------------------------
# 阅读 + 评价
# -------------------------
@app.route("/review/<doc_id>", methods=["GET","POST"])
def review(doc_id):
    if "user" not in session:
        return redirect("/")

    config = load_json(CONFIG_FILE)
    questions = config.get("questions", [])

    doc_path = os.path.join(DOC_FOLDER, doc_id)
    if not os.path.exists(doc_path):
        return "文件不存在"

    doc_url = url_for('serve_document', filename=doc_id)

    # 记录访问开始时间
    if request.method == "GET":
        session['start_review_time'] = time.time()

    if request.method=="POST":
        # 后端验证强制阅读时间
        if time.time() - session.get('start_review_time',0) < 10:
            return "请先认真阅读文档再提交"

        reviews = load_json("reviews.json")
        reviews.setdefault(doc_id, [])

        entry = {"user": session["user"]}
        for q in questions:
            score = request.form.get(q["id"], 0)
            entry[q["id"]] = score
        entry["comment"] = request.form.get("comment", "")
        reviews[doc_id].append(entry)
        save_json("reviews.json", reviews)

        # 提交后移除该文档
        if "random_docs" in session:
            session["random_docs"] = [d for d in session["random_docs"] if d["id"] != doc_id]

        return redirect("/dashboard")

    return render_template("review.html", doc_id=doc_id, questions=questions, doc_url=doc_url)

# -------------------------
# 管理员后台
# -------------------------
@app.route("/admin")
def admin():
    if "user" not in session or session["user"] != "admin":
        return "无权限"

    reviews = load_json("reviews.json")
    config = load_json(CONFIG_FILE)
    questions = config.get("questions", [])

    stats = {}
    for doc, data in reviews.items():
        doc_stats = {}
        for q in questions:
            scores = [int(r.get(q["id"],0)) for r in data]
            doc_stats[q["id"]] = round(sum(scores)/len(scores),2) if scores else 0
        stats[doc] = doc_stats

    return render_template("admin.html", reviews=reviews, stats=stats, questions=questions)

# -------------------------
# Excel 导出
# -------------------------
@app.route("/export")
def export():
    if "user" not in session or session["user"] != "admin":
        return "无权限"

    reviews = load_json("reviews.json")
    config = load_json(CONFIG_FILE)
    questions = config.get("questions", [])

    rows = []
    for doc, data in reviews.items():
        for r in data:
            row = {"document": doc, "user": r["user"], "comment": r.get("comment","")}
            for q in questions:
                row[q["id"]] = r.get(q["id"],0)
            rows.append(row)

    df = pd.DataFrame(rows)
    file = "reviews.xlsx"
    df.to_excel(file, index=False)
    return send_file(file, as_attachment=True)

# -------------------------
# 文档上传
# -------------------------
@app.route("/upload", methods=["POST"])
def upload():
    if "user" not in session or session["user"] != "admin":
        return "无权限"
    f = request.files["file"]
    path = os.path.join(DOC_FOLDER, f.filename)
    f.save(path)
    return redirect("/dashboard")

# -------------------------
# 退出
# -------------------------
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

# -------------------------
# 主程序
# -------------------------
if __name__=="__main__":
    if not os.path.exists(DOC_FOLDER):
        os.mkdir(DOC_FOLDER)
    port = int(os.environ.get("PORT",5000))
    app.run(host="0.0.0.0", port=port)
