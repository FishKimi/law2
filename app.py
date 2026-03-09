from flask import Flask, render_template, request, redirect, session, send_file, url_for
import os, json, pandas as pd, qrcode
from io import BytesIO

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY","doc_review_platform")

DOC_FOLDER = "documents"
os.makedirs(DOC_FOLDER, exist_ok=True)
for f in ["users.json","reviews.json"]:
    if not os.path.exists(f):
        with open(f,"w",encoding="utf-8") as fp:
            fp.write("{}")

# -------------------------
# 工具函数
# -------------------------
def load_json(file):
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
            docs.append({"id":f,"name":f})
    return docs

def generate_qr(doc_id):
    """生成文档评价二维码"""
    review_url = url_for("review", doc_id=doc_id, _external=True)
    img = qrcode.make(review_url)
    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf

# -------------------------
# 路由
# -------------------------

@app.route("/",methods=["GET","POST"])
def login():
    if request.method=="POST":
        username=request.form["username"]
        password=request.form["password"]
        users=load_json("users.json")
        if username in users and users[username]==password:
            session["user"]=username
            return redirect("/dashboard")
        return "用户名或密码错误"
    return render_template("login.html")

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

@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect("/")
    docs = get_documents()
    return render_template("dashboard.html", docs=docs, user=session["user"])

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
        reviews.setdefault(doc_id,[]).append({
            "user":session["user"],
            "readability":readability,
            "professionalism":professionalism,
            "completeness":completeness,
            "comment":comment
        })
        save_json("reviews.json",reviews)
        return redirect("/dashboard")
    return render_template("review.html",doc_id=doc_id)

@app.route("/admin")
def admin():
    if "user" not in session or session["user"]!="admin":
        return "无权限"
    reviews=load_json("reviews.json")
    stats={}
    for doc,data in reviews.items():
        r=[int(x["readability"]) for x in data]
        p=[int(x["professionalism"]) for x in data]
        c=[int(x["completeness"]) for x in data]
        stats[doc] = {
            "readability":round(sum(r)/len(r),2),
            "professionalism":round(sum(p)/len(p),2),
            "completeness":round(sum(c)/len(c),2)
        }
    docs = get_documents()
    return render_template("admin.html", reviews=reviews, stats=stats, docs=docs)

@app.route("/export")
def export():
    if "user" not in session or session["user"]!="admin":
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

@app.route("/upload",methods=["POST"])
def upload():
    if "user" not in session or session["user"]!="admin":
        return "无权限"
    f=request.files["file"]
    f.save(os.path.join(DOC_FOLDER,f.filename))
    return redirect("/dashboard")

@app.route("/qr/<doc_id>")
def qr(doc_id):
    if "user" not in session or session["user"]!="admin":
        return "无权限"
    buf = generate_qr(doc_id)
    return send_file(buf, mimetype="image/png")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

# -------------------------
# 本地开发 / 生产启动
# -------------------------
if __name__=="__main__":
    port=int(os.environ.get("PORT",5000))
    app.run(host="0.0.0.0", port=port)
