from flask import Flask, render_template, request, redirect, session, send_file, url_for
import json
import os
import pandas as pd
import random

app = Flask(__name__)
app.secret_key = "doc_review_platform"

DOC_FOLDER = "documents"

# -------------------------
# 工具函数
# -------------------------
def load_json(file):
    if not os.path.exists(file):
        return {}
    with open(file,"r",encoding="utf-8") as f:
        try:
            return json.load(f)
        except:
            return {}

def save_json(file,data):
    with open(file,"w",encoding="utf-8") as f:
        json.dump(data,f,indent=4,ensure_ascii=False)

def get_documents():
    docs = []
    for f in os.listdir(DOC_FOLDER):
        if f.endswith(".pdf") or f.endswith(".docx"):
            docs.append({
                "id":f,
                "name":f
            })
    return docs

# -------------------------
# 登录
# -------------------------
@app.route("/",methods=["GET","POST"])
def login():
    if request.method=="POST":
        username=request.form["username"]
        password=request.form["password"]
        users=load_json("users.json")
        if username in users and users[username]==password:
            session["user"]=username
            session.pop("random_docs", None)  # 清除旧随机列表
            return redirect("/dashboard")
        return "用户名或密码错误"
    return render_template("login.html")

# -------------------------
# 注册
# -------------------------
@app.route("/register",methods=["GET","POST"])
def register():
    if request.method=="POST":
        username=request.form["username"]
        password=request.form["password"]
        users=load_json("users.json")
        if username in users:
            return "用户已存在"
        users[username]=password
        save_json("users.json",users)
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
# 文档下载/阅读
# -------------------------
@app.route("/documents/<filename>")
def serve_document(filename):
    if "user" not in session:
        return redirect("/")
    path = os.path.join(DOC_FOLDER, filename)
    if not os.path.exists(path):
        return "文件不存在"
    return send_file(path, as_attachment=True)

# -------------------------
# 阅读 + 评价
# -------------------------
@app.route("/review/<doc_id>",methods=["GET","POST"])
def review(doc_id):
    if "user" not in session:
        return redirect("/")

    if request.method=="POST":
        readability=request.form["readability"]
        professionalism=request.form["professionalism"]
        completeness=request.form["completeness"]
        comment=request.form["comment"]

        reviews=load_json("reviews.json")
        reviews.setdefault(doc_id,[])
        reviews[doc_id].append({
            "user":session["user"],
            "readability":readability,
            "professionalism":professionalism,
            "completeness":completeness,
            "comment":comment
        })
        save_json("reviews.json",reviews)

        # 提交后移除该文档，保持剩余文档列表
        if "random_docs" in session:
            session["random_docs"] = [d for d in session["random_docs"] if d["id"] != doc_id]

        return redirect("/dashboard")

    return render_template("review.html", doc_id=doc_id)

# -------------------------
# 管理员后台
# -------------------------
@app.route("/admin")
def admin():
    if "user" not in session:
        return redirect("/")
    if session["user"]!="admin":
        return "无权限"

    reviews=load_json("reviews.json")
    stats={}
    for doc,data in reviews.items():
        r=[int(x["readability"]) for x in data]
        p=[int(x["professionalism"]) for x in data]
        c=[int(x["completeness"]) for x in data]
        stats[doc]={
            "readability":round(sum(r)/len(r),2),
            "professionalism":round(sum(p)/len(p),2),
            "completeness":round(sum(c)/len(c),2)
        }

    return render_template("admin.html", reviews=reviews, stats=stats)

# -------------------------
# Excel 导出
# -------------------------
@app.route("/export")
def export():
    if "user" not in session or session["user"] != "admin":
        return "无权限"

    reviews=load_json("reviews.json")
    rows=[]
    for doc,data in reviews.items():
        for r in data:
            rows.append({
                "document":doc,
                "user":r["user"],
                "readability":r["readability"],
                "professionalism":r["professionalism"],
                "completeness":r["completeness"],
                "comment":r["comment"]
            })

    df=pd.DataFrame(rows)
    file="reviews.xlsx"
    df.to_excel(file,index=False)
    return send_file(file,as_attachment=True)

# -------------------------
# 文档上传
# -------------------------
@app.route("/upload",methods=["POST"])
def upload():
    if "user" not in session or session["user"]!="admin":
        return "无权限"

    f=request.files["file"]
    path=os.path.join(DOC_FOLDER,f.filename)
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
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
