from flask import Flask,render_template,request,redirect,session,url_for,send_file
import os,json,random,time,pandas as pd
from docx2pdf import convert

app=Flask(__name__)
app.secret_key="review_system"

DOC_FOLDER="documents"
CONFIG_FILE="config.json"

MAX_ASSIGN_PER_DOC=5
DOCS_PER_USER=5
READ_TIME=10


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

    docs=[]

    for f in os.listdir(DOC_FOLDER):

        if f.endswith(".pdf"):

            docs.append({"id":f,"name":f})

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
            session.pop("random_docs",None)

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
# 文档分配算法
# -------------------------

def assign_documents(user):

    docs=get_documents()

    assignments=load_json("doc_assignments.json")
    history=load_json("user_history.json")

    history.setdefault(user,[])

    for d in docs:
        assignments.setdefault(d["id"],0)

    available=[

        d for d in docs

        if assignments[d["id"]]<MAX_ASSIGN_PER_DOC
        and d["id"] not in history[user]

    ]

    if len(available)==0:
        return []

    available.sort(key=lambda x:assignments[x["id"]])

    min_count=assignments[available[0]["id"]]

    candidate=[

        d for d in available
        if assignments[d["id"]]==min_count

    ]

    if len(candidate)<DOCS_PER_USER:

        candidate=available

    selected=random.sample(candidate,min(DOCS_PER_USER,len(candidate)))

    for d in selected:

        assignments[d["id"]]+=1
        history[user].append(d["id"])

    save_json("doc_assignments.json",assignments)
    save_json("user_history.json",history)

    return selected


# -------------------------
# Dashboard
# -------------------------

@app.route("/dashboard")
def dashboard():

    if "user" not in session:
        return redirect("/")

    user=session["user"]

    docs=get_documents()

    if user=="admin":

        return render_template("dashboard.html",docs=docs,user=user)

    if "random_docs" not in session:

        session["random_docs"]=assign_documents(user)

    docs=session["random_docs"]

    if len(docs)==0:

        return "所有文档已完成评价"

    return render_template("dashboard.html",docs=docs,user=user)


# -------------------------
# 文档显示
# -------------------------

@app.route("/documents/<filename>")
def serve_document(filename):

    path=os.path.join(DOC_FOLDER,filename)

    return send_file(path,mimetype="application/pdf",as_attachment=False)


# -------------------------
# 文档评价
# -------------------------

@app.route("/review/<doc_id>",methods=["GET","POST"])
def review(doc_id):

    if "user" not in session:
        return redirect("/")

    config=load_json(CONFIG_FILE)

    questions=config.get("questions",[])

    doc_url=url_for("serve_document",filename=doc_id)

    if request.method=="GET":

        session["start_time"]=time.time()

    if request.method=="POST":

        if time.time()-session.get("start_time",0)<READ_TIME:

            return "阅读时间不足"

        reviews=load_json("reviews.json")

        reviews.setdefault(doc_id,[])

        entry={"user":session["user"]}

        for q in questions:

            entry[q["id"]]=request.form.get(q["id"],0)

        entry["comment"]=request.form.get("comment","")

        reviews[doc_id].append(entry)

        save_json("reviews.json",reviews)

        session["random_docs"]=[

            d for d in session["random_docs"]

            if d["id"]!=doc_id

        ]

        return redirect("/dashboard")

    return render_template("review.html",doc_url=doc_url,questions=questions)


# -------------------------
# 文档上传
# -------------------------

@app.route("/upload",methods=["POST"])
def upload():

    if session.get("user")!="admin":

        return "无权限"

    f=request.files["file"]

    filename=f.filename

    ext=filename.split(".")[-1].lower()

    path=os.path.join(DOC_FOLDER,filename)

    f.save(path)

    if ext=="docx":

        pdf_name=filename.replace(".docx",".pdf")

        pdf_path=os.path.join(DOC_FOLDER,pdf_name)

        convert(path,pdf_path)

        os.remove(path)

    return redirect("/dashboard")


# -------------------------
# 管理员后台
# -------------------------

@app.route("/admin")
def admin():

    if session.get("user")!="admin":

        return "无权限"

    reviews=load_json("reviews.json")

    config=load_json(CONFIG_FILE)

    questions=config.get("questions",[])

    stats={}

    for doc,data in reviews.items():

        stats[doc]={}

        for q in questions:

            scores=[int(r[q["id"]]) for r in data]

            stats[doc][q["id"]]=round(sum(scores)/len(scores),2)

    return render_template("admin.html",
                           reviews=reviews,
                           stats=stats,
                           questions=questions)


# -------------------------
# 管理员监控
# -------------------------

@app.route("/monitor")
def monitor():

    if session.get("user")!="admin":

        return "无权限"

    docs=get_documents()

    assignments=load_json("doc_assignments.json")

    data=[]

    for d in docs:

        count=assignments.get(d["id"],0)

        data.append({

            "doc":d["id"],
            "count":count,
            "remaining":MAX_ASSIGN_PER_DOC-count,
            "progress":round(count/MAX_ASSIGN_PER_DOC*100,1)

        })

    total_required=len(docs)*MAX_ASSIGN_PER_DOC
    total_done=sum(assignments.values())

    return render_template("monitor.html",
                           data=data,
                           total_done=total_done,
                           total_required=total_required)


# -------------------------
# 导出Excel
# -------------------------

@app.route("/export")
def export():

    if session.get("user")!="admin":

        return "无权限"

    reviews=load_json("reviews.json")

    rows=[]

    for doc,data in reviews.items():

        for r in data:

            r["document"]=doc
            rows.append(r)

    df=pd.DataFrame(rows)

    file="reviews.xlsx"

    df.to_excel(file,index=False)

    return send_file(file,as_attachment=True)


# -------------------------

if __name__=="__main__":

    if not os.path.exists(DOC_FOLDER):
        os.mkdir(DOC_FOLDER)

    port=int(os.environ.get("PORT",5000))

    app.run(host="0.0.0.0",port=port)
